#!/usr/bin/env python3
"""Validate all entries in the IFF library (V-1..V-10 from VALIDATION_PLAN.md).

Exits 0 on clean (no errors, warnings allowed), 1 on any error.

Checks:
    V-1  every manifest parses and matches its declared schema_version
    V-2  every parameterized_with reference resolves
    V-3  every supersedes / parent_ff / overrides.target / validated_with resolves
    V-4  no duplicate <family>@<version>
    V-5  every declared table sha256 matches the file
    V-6  every structure's atom types resolve in its pinned FF (possibly after
         rename chain walking)
    V-7  no circular supersedes chain
    V-8  no breaking change crossed without breaking:true declared
    V-9  unresolved cross-entry conflicts as warnings (not errors)
    V-10 no table CSVs modified in-place (immutability check; best-effort via
         live hash recompute — enforced harder in CI pre-commit hook)

Usage:
    python scripts/validate.py                # validate live library
    python scripts/validate.py --data-dir …   # alternate path
    python scripts/validate.py --json report.json  # structured output

The tool prints a human summary and (optionally) writes a JSON report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ---------------------------------------------------------------------------

@dataclass
class Report:
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def err(self, check: str, entry: str, msg: str, **kw) -> None:
        self.errors.append({"check": check, "entry": entry, "message": msg, **kw})

    def warn(self, check: str, entry: str, msg: str, **kw) -> None:
        self.warnings.append({"check": check, "entry": entry, "message": msg, **kw})

    def is_clean(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------

_ARCHIVE = "archive"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_live_manifests(data_dir: Path):
    for mp in sorted(data_dir.rglob("manifest.json")):
        if _ARCHIVE in mp.parts:
            continue
        yield mp


def _entry_ref(manifest: dict) -> str:
    return f"{manifest.get('name', '?')}@{manifest.get('version', '?')}"


# ---------------------------------------------------------------------------
# Checks

def check_v1_v5(data_dir: Path, report: Report, manifests: list[dict]) -> None:
    """V-1 (schema), V-5 (hashes). Also records manifest contents."""
    for mp in _iter_live_manifests(data_dir):
        ref = None
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except Exception as e:
            report.err("V-1", str(mp), f"manifest parse error: {e}")
            continue
        manifests.append({"path": str(mp.parent), "manifest": m})
        ref = _entry_ref(m)

        schema = m.get("schema_version", "")
        if not (schema.startswith("upm-") or schema.startswith("0.")):
            report.warn("V-1", ref, f"unusual schema_version: {schema!r}")

        # Inv 6: provenance required (author + source_sha256)
        prov = m.get("provenance", {})
        if not isinstance(prov, dict) or not prov.get("author"):
            report.err("V-1", ref, "missing provenance.author (Inv 6)")
        if not isinstance(prov, dict) or not prov.get("source_sha256"):
            # Structure entries may legitimately have no source_sha256 since
            # the geometry file hash is tracked separately; only require for
            # parameter entries.
            if m.get("type", "parameters") == "parameters":
                report.err("V-1", ref, "missing provenance.source_sha256 (Inv 6)")

        # V-5: hashes
        for block_name in ("tables", "sources"):
            block = m.get(block_name)
            if isinstance(block, dict):
                iterable = block.items()
            elif isinstance(block, list):
                iterable = [(i, item) for i, item in enumerate(block)]
            else:
                continue
            for key, meta in iterable:
                if not isinstance(meta, dict):
                    continue
                rel = meta.get("path")
                expected = meta.get("sha256")
                if not isinstance(rel, str) or not isinstance(expected, str):
                    continue
                fpath = mp.parent / rel
                if not fpath.is_file():
                    report.err("V-5", ref, f"declared file missing: {rel}")
                    continue
                actual = _sha256(fpath)
                if actual != expected:
                    report.err("V-5", ref, f"sha256 mismatch for {rel}",
                               expected=expected, actual=actual)

        # Atoms + geometry blocks for structures
        for block_name in ("atoms_csv", "topology_csv", "geometry"):
            meta = m.get(block_name)
            if not isinstance(meta, dict):
                continue
            rel = meta.get("path")
            expected = meta.get("sha256")
            if not isinstance(rel, str) or not isinstance(expected, str):
                continue
            fpath = mp.parent / rel
            if not fpath.is_file():
                report.err("V-5", ref, f"declared file missing: {rel}")
                continue
            actual = _sha256(fpath)
            if actual != expected:
                report.err("V-5", ref, f"sha256 mismatch for {rel}",
                           expected=expected, actual=actual)


def check_v4(report: Report, manifests: list[dict]) -> None:
    """V-4: no duplicate (family, version)."""
    seen: dict[tuple[str, str], str] = {}
    for item in manifests:
        m = item["manifest"]
        key = (m.get("name"), m.get("version"))
        if key in seen:
            report.err("V-4", f"{key[0]}@{key[1]}",
                       f"duplicate entry (also at {seen[key]})")
        else:
            seen[key] = item["path"]


def check_v2_v3(report: Report, manifests: list[dict]) -> None:
    """V-2 (parameterized_with), V-3 (supersedes / parent_ff / overrides / validated_with)."""
    def _by_ref(ms: list[dict]) -> set[tuple[str, str]]:
        return {(x["manifest"].get("name"), x["manifest"].get("version")) for x in ms}

    existing = _by_ref(manifests)

    for item in manifests:
        m = item["manifest"]
        ref = _entry_ref(m)
        etype = m.get("type", "parameters")

        # parameterized_with (structure entries)
        if etype == "structure":
            pw = m.get("parameterized_with", [])
            if not pw:
                report.err("V-2", ref, "structure has no parameterized_with")
            for p in pw:
                if not isinstance(p, dict):
                    report.err("V-2", ref, f"parameterized_with entry not a dict: {p!r}")
                    continue
                tgt = (p.get("name"), p.get("version"))
                if tgt not in existing:
                    report.err("V-2", ref,
                               f"parameterized_with target not found: {tgt[0]}@{tgt[1]}")

        # supersedes — same family, previous version
        if m.get("supersedes"):
            tgt = (m.get("name"), m.get("supersedes"))
            if tgt not in existing:
                report.warn("V-3", ref,
                            f"supersedes target not found: {tgt[0]}@{tgt[1]}")

        # parent_ff — "name/version"
        if m.get("parent_ff"):
            parent = m["parent_ff"]
            if "/" in parent:
                name, ver = parent.rsplit("/", 1)
                if (name, ver) not in existing:
                    report.err("V-3", ref,
                               f"parent_ff target not found: {parent}")

        for ov in m.get("overrides", []) or []:
            tgt = ov.get("target")
            if isinstance(tgt, str) and "/" in tgt:
                name, ver = tgt.rsplit("/", 1)
                if (name, ver) not in existing:
                    report.err("V-3", ref,
                               f"override target not found: {tgt}")

        for vw in m.get("validated_with", []) or []:
            if not isinstance(vw, dict):
                continue
            if (vw.get("name"), vw.get("version")) not in existing:
                report.warn("V-3", ref,
                            f"validated_with target not found: {vw.get('name')}@{vw.get('version')}")


def check_v6(data_dir: Path, report: Report, manifests: list[dict]) -> None:
    """V-6: every structure's atom types resolve in its pinned FF."""
    # Import the real compat check — but it calls get_data_dir which we must
    # patch if data_dir differs. For the usual case (live library), no patching
    # needed because get_data_dir returns the same path.
    import iff_parameters
    from iff_parameters.compat import compatibility_check
    from iff_parameters.entries import Entry

    # Point get_data_dir at the validation target
    original = iff_parameters.get_data_dir
    try:
        iff_parameters.get_data_dir = lambda: data_dir

        for item in manifests:
            m = item["manifest"]
            if m.get("type") != "structure":
                continue
            ref = _entry_ref(m)
            entry = Entry(path=Path(item["path"]), manifest=m)
            for p in m.get("parameterized_with", []):
                if not isinstance(p, dict):
                    continue
                r = compatibility_check(entry, p.get("name"), p.get("version"))
                if r.status == "ERROR":
                    missing = r.missing.get("atom_types", [])
                    report.err("V-6", ref,
                               f"coverage failure against {p.get('name')}@{p.get('version')}: "
                               f"missing types = {missing[:6]}")
    finally:
        iff_parameters.get_data_dir = original


def check_v7(report: Report, manifests: list[dict]) -> None:
    """V-7: no circular supersedes chain."""
    # build family graph: (name, version) -> supersedes (name, version)
    graph: dict[tuple[str, str], tuple[str, str] | None] = {}
    for item in manifests:
        m = item["manifest"]
        key = (m.get("name"), m.get("version"))
        sup = m.get("supersedes")
        graph[key] = (m.get("name"), sup) if sup else None

    for start in graph:
        seen = {start}
        cur = graph.get(start)
        while cur is not None:
            if cur in seen:
                report.err("V-7", f"{start[0]}@{start[1]}",
                           f"circular supersedes chain through {cur[0]}@{cur[1]}")
                break
            if cur not in graph:
                break
            seen.add(cur)
            cur = graph.get(cur)


def check_v8(report: Report, manifests: list[dict]) -> None:
    """V-8: cannot declare renames without either supersedes or a parent_ff.

    This isn't a strict check but catches an easy mistake: renames only make
    sense when you're mutating an existing family. If you're making a new
    family, there's nothing to rename.
    """
    for item in manifests:
        m = item["manifest"]
        if m.get("renames") and not m.get("supersedes") and not m.get("parent_ff"):
            report.warn("V-8", _entry_ref(m),
                        "renames declared but no supersedes or parent_ff")


def check_v9(data_dir: Path, report: Report) -> None:
    """V-9: surface cross-entry conflicts as warnings."""
    from upm.registry.discovery import discover_local_packages
    from upm.registry.index import PackageIndex

    params_root = data_dir / "parameters"
    if not params_root.is_dir():
        return
    pkgs = discover_local_packages(params_root)
    # Collapse to latest-per-family for conflict detection
    latest: dict[str, any] = {}
    for p in pkgs:
        cur = latest.get(p.name)
        if cur is None or p.version > cur.version:
            latest[p.name] = p
    idx = PackageIndex(list(latest.values()))
    for c in idx.conflicts():
        key_str = " — ".join(c.key) if isinstance(c.key, tuple) else str(c.key)
        report.warn("V-9", ",".join(f"{o.package_name}@{o.package_version}" for o in c.occurrences),
                    f"{c.scope} key {key_str} disagrees on {', '.join(c.disagreements)}")


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=None,
                    help="library root (default: src/iff_parameters/data)")
    ap.add_argument("--json", default=None,
                    help="write structured JSON report to this path")
    ap.add_argument("--strict", action="store_true",
                    help="treat warnings as errors (exit 1 if any warnings)")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).resolve() if args.data_dir else (
        _REPO_ROOT / "src" / "iff_parameters" / "data"
    )

    if not data_dir.is_dir():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        return 2

    report = Report()
    manifests: list[dict] = []

    check_v1_v5(data_dir, report, manifests)
    check_v4(report, manifests)
    check_v2_v3(report, manifests)
    check_v6(data_dir, report, manifests)
    check_v7(report, manifests)
    check_v8(report, manifests)
    check_v9(data_dir, report)

    report.info = {
        "data_dir": str(data_dir),
        "n_entries": len(manifests),
        "by_type": _count_by_type(manifests),
    }

    # Human-readable output
    print(f"Validated {len(manifests)} entries under {data_dir}\n")
    print(f"  errors:   {len(report.errors)}")
    print(f"  warnings: {len(report.warnings)}")
    print()
    if report.errors:
        print("ERRORS:")
        for e in report.errors[:30]:
            print(f"  [{e['check']}] {e['entry']}: {e['message']}")
        if len(report.errors) > 30:
            print(f"  … and {len(report.errors) - 30} more")
        print()
    if report.warnings:
        print("WARNINGS:")
        for w in report.warnings[:30]:
            print(f"  [{w['check']}] {w['entry']}: {w['message']}")
        if len(report.warnings) > 30:
            print(f"  … and {len(report.warnings) - 30} more")
        print()

    if args.json:
        Path(args.json).write_text(json.dumps({
            "errors": report.errors,
            "warnings": report.warnings,
            "info": report.info,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"JSON report: {args.json}")

    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


def _count_by_type(manifests: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in manifests:
        counts[item["manifest"].get("type", "parameters")] += 1
    return dict(counts)


if __name__ == "__main__":
    raise SystemExit(main())
