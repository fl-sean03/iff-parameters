#!/usr/bin/env python3
"""Batch-ingest all .frc and .prm files from a directory.

Usage:
    python scripts/batch_ingest.py --scan-dir canonical_sources/
    python scripts/batch_ingest.py --scan-dir ~/Dropbox/forcefields/ --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


def _name_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    name = stem.replace("_", "-").replace("+", "-").lower()
    while "--" in name:
        name = name.replace("--", "-")
    return name.strip("-")


def _load_ingested_hashes(data_dir: Path) -> set[str]:
    hashes: set[str] = set()
    if not data_dir.is_dir():
        return hashes
    for mp in data_dir.rglob("manifest.json"):
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
            h = m.get("provenance", {}).get("source_sha256", "")
            if h:
                hashes.add(h)
        except Exception:
            continue
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-ingest .frc and .prm files")
    parser.add_argument("--scan-dir", required=True)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--version", default="v1.0")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scan_dir = Path(args.scan_dir).resolve()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else _REPO_ROOT / "src" / "iff_parameters" / "data"

    files = sorted(list(scan_dir.glob("*.frc")) + list(scan_dir.glob("*.prm")))
    if not files:
        print(f"No .frc or .prm files found in {scan_dir}")
        return

    print(f"Found {len(files)} files in {scan_dir}")
    existing = _load_ingested_hashes(data_dir)
    print(f"Already ingested: {len(existing)} bundles\n")

    from iff_parameters._provenance import sha256_of_file, CANONICAL_PROVENANCE, Provenance

    ok, skip, fail = 0, 0, 0
    for src in files:
        file_hash = sha256_of_file(src)
        name = _name_from_filename(src.name)

        if file_hash in existing:
            print(f"  SKIP  {src.name} (duplicate)")
            skip += 1
            continue

        if args.dry_run:
            print(f"  WOULD {src.name} -> {name}@{args.version}")
            continue

        defaults = CANONICAL_PROVENANCE.get(src.name, {})
        try:
            fmt = "frc" if src.suffix.lower() == ".frc" else "prm"
            source_text = src.read_text(encoding="utf-8")

            if fmt == "frc":
                from upm.codecs.msi_frc import parse_frc_text
                tables, raw = parse_frc_text(source_text, validate=False)
            else:
                from upm.codecs._charmm_parser import parse_prm_text
                tables, raw = parse_prm_text(source_text)
                from upm.core.tables import normalize_tables
                tables = normalize_tables(tables)

            from upm.bundle.io import save_package
            root = data_dir / name / args.version
            units = {"length": "angstrom", "energy": "kcal/mol", "mass": "amu", "angle": "degree"}
            nb = {"style": "A-B", "form": "12-6", "mixing": "geometric"} if fmt == "frc" else {"style": "eps-rmin", "form": "12-6", "mixing": "arithmetic"}

            save_package(root, name=name, version=args.version, tables=tables,
                         source_text=source_text, unknown_sections=raw, units=units, nonbonded=nb)

            prov = Provenance(
                author=defaults.get("author", "Unknown"),
                lab=defaults.get("lab", "Heinz Lab, CU Boulder"),
                date_created=defaults.get("date_created", ""),
                publication_doi=defaults.get("publication_doi"),
                source_file=src.name, source_sha256=file_hash,
                parent_ff=defaults.get("parent_ff"),
                materials=defaults.get("materials", []),
                notes=defaults.get("notes", ""),
            )
            mp = root / "manifest.json"
            m = json.loads(mp.read_text(encoding="utf-8"))
            m["provenance"] = prov.to_dict()
            mp.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            summary = {k: len(v) for k, v in tables.items()}
            print(f"  OK    {src.name} -> {name}@{args.version} {summary}")
            ok += 1

        except Exception as e:
            print(f"  FAIL  {src.name}: {e}")
            fail += 1

    print(f"\n{'='*50}")
    print(f"Ingested: {ok} | Skipped: {skip} | Failed: {fail}")


if __name__ == "__main__":
    main()
