"""Seed the library with the three canonical parameter bundles from INTERFACE_FF_1_5.

Writes:
    data/parameters/cvff-interface/v1.5/
    data/parameters/pcff-interface/v1.5/     (partial_roundtrip=True)
    data/parameters/charmm27-interface/v1.5/

Idempotent: running twice leaves the same bytes on disk (modulo the
``created_utc`` timestamp in the manifest). Use --force to overwrite.

Logs its actions to `data/parameters/_seed_log.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / "canonical_sources" / "INTERFACE_FF_1_5" / "FORCE_FIELDS"
DATA_DIR = REPO_ROOT / "src" / "iff_parameters" / "data"

# (family_name, source_filename, source_format, partial_roundtrip, materials)
PARAMETER_SEEDS = [
    (
        "cvff-interface",
        "cvff_interface_v1_5.frc",
        "frc",
        False,
        ["silica", "clay", "metals", "cement", "hydroxyapatite", "Ca sulfate", "PEO"],
    ),
    (
        "pcff-interface",
        "pcff_interface_v1_5.frc",
        "frc",
        True,  # 9-6 nonbond + cross terms not fully parsed
        ["silica", "clay", "metals", "cement", "hydroxyapatite", "Ca sulfate", "PEO"],
    ),
    (
        "charmm27-interface",
        "charmm27_interface_v1_5.prm",
        "prm",
        False,
        ["silica", "clay", "metals", "cement", "hydroxyapatite", "Ca sulfate", "PEO"],
    ),
]

VERSION = "v1.5"


@dataclass
class SeedResult:
    family: str
    version: str
    source_file: str
    source_sha256: str
    path: str
    n_atom_types: int
    n_bonds: int
    n_angles: int
    n_torsions: int
    partial_roundtrip: bool


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_source(path: Path, fmt: str):
    text = path.read_text(encoding="utf-8", errors="replace")
    if fmt == "frc":
        from upm.codecs.msi_frc import parse_frc_text
        tables, raw = parse_frc_text(text, validate=False)
    elif fmt == "prm":
        from upm.codecs._charmm_parser import parse_prm_text
        from upm.core.tables import normalize_tables
        tables, raw = parse_prm_text(text)
        tables = normalize_tables(tables)
    else:
        raise ValueError(f"unknown format: {fmt}")
    return text, tables, raw


def seed_one(family: str, source_name: str, fmt: str, partial_rt: bool,
             materials: list[str], *, force: bool = False) -> SeedResult:
    source_path = CANONICAL_DIR / source_name
    if not source_path.is_file():
        raise FileNotFoundError(f"canonical source missing: {source_path}")

    target_root = DATA_DIR / "parameters" / family / VERSION
    if target_root.exists():
        if not force:
            print(f"  skip {family}@{VERSION}: already exists (use --force to overwrite)")
            return _load_existing_result(family, target_root, source_path, partial_rt)
        print(f"  overwriting existing {family}@{VERSION}")
        shutil.rmtree(target_root)

    text, tables, raw = _parse_source(source_path, fmt)
    source_sha = _sha256_file(source_path)

    provenance = {
        "author": "Hendrik Heinz",
        "lab": "Heinz Lab, CU Boulder",
        "date_created": "2014-04-14",
        "source_file": source_name,
        "source_sha256": source_sha,
        "materials": materials,
        "notes": (
            "Canonical INTERFACE Force Field v1.5 (April 2014). "
            "Distribution documented at http://bionanostructures.com/."
            + (" Partial roundtrip: 9-6 nonbond / cross-terms preserved as raw only."
               if partial_rt else "")
        ),
        "ingested_utc": datetime.now(timezone.utc)
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "publication_doi": None,
    }

    nonbonded = (
        {"style": "A-B", "form": "12-6", "mixing": "geometric"} if fmt == "frc"
        else {"style": "eps-rmin", "form": "12-6", "mixing": "arithmetic"}
    )
    if family == "pcff-interface":
        nonbonded = {"style": "A-B", "form": "9-6", "mixing": "sixth-power",
                     "note": "9-6 nonbond not fully parseable; see raw/source.frc"}

    from upm.bundle.io import save_package
    save_package(
        target_root,
        name=family, version=VERSION,
        tables=tables,
        source_text=text,
        source_format=fmt,
        unknown_sections=raw,
        nonbonded=nonbonded,
        provenance=provenance,
        partial_roundtrip=partial_rt,
    )

    return SeedResult(
        family=family,
        version=VERSION,
        source_file=source_name,
        source_sha256=source_sha,
        path=str(target_root.relative_to(REPO_ROOT)),
        n_atom_types=len(tables.get("atom_types", [])),
        n_bonds=len(tables.get("bonds", [])),
        n_angles=len(tables.get("angles", [])),
        n_torsions=len(tables.get("torsions", [])),
        partial_roundtrip=partial_rt,
    )


def _load_existing_result(family: str, target_root: Path, source_path: Path,
                          partial_rt: bool) -> SeedResult:
    """Construct a SeedResult from an already-written bundle (for idempotent runs)."""
    manifest = json.loads((target_root / "manifest.json").read_text())
    tables = manifest.get("tables", {})
    return SeedResult(
        family=family,
        version=VERSION,
        source_file=source_path.name,
        source_sha256=_sha256_file(source_path),
        path=str(target_root.relative_to(REPO_ROOT)),
        n_atom_types=tables.get("atom_types", {}).get("rows", 0),
        n_bonds=tables.get("bonds", {}).get("rows", 0),
        n_angles=tables.get("angles", {}).get("rows", 0),
        n_torsions=tables.get("torsions", {}).get("rows", 0),
        partial_roundtrip=partial_rt,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing bundles")
    args = ap.parse_args()

    if not CANONICAL_DIR.is_dir():
        print(f"ERROR: canonical source dir not found: {CANONICAL_DIR}", file=sys.stderr)
        print("Did you place INTERFACE_FF_1_5 at canonical_sources/?", file=sys.stderr)
        return 2

    (DATA_DIR / "parameters").mkdir(parents=True, exist_ok=True)

    print(f"Seeding parameter bundles from {CANONICAL_DIR}")
    print(f"Target:   {DATA_DIR / 'parameters'}")
    print()

    results: list[SeedResult] = []
    for family, source_name, fmt, partial_rt, materials in PARAMETER_SEEDS:
        print(f"Ingesting {family} from {source_name}...")
        try:
            r = seed_one(family, source_name, fmt, partial_rt, materials, force=args.force)
            results.append(r)
            print(f"  -> {r.path}  atoms={r.n_atom_types} bonds={r.n_bonds} "
                  f"angles={r.n_angles} torsions={r.n_torsions}"
                  f"{'  [partial_roundtrip]' if r.partial_roundtrip else ''}")
        except Exception as e:
            print(f"  !! FAILED: {e}")
            return 1

    log_path = DATA_DIR / "parameters" / "_seed_log.json"
    log_path.write_text(json.dumps({
        "seeded_utc": datetime.now(timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"),
        "results": [asdict(r) for r in results],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print(f"Log written to {log_path.relative_to(REPO_ROOT)}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
