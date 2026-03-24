#!/usr/bin/env python3
"""Ingest a single .frc or .prm file into a versioned UPM bundle.

Usage:
    python scripts/ingest.py \
        --path canonical_sources/cvff_interface_v1_5.frc \
        --name cvff-interface-v1-5 \
        --version v1.0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


def _parse_file(path: Path) -> tuple[dict, list, str, str]:
    """Parse a FF file. Returns (tables, raw_sections, source_text, fmt)."""
    source_text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".frc":
        from upm.codecs.msi_frc import parse_frc_text
        tables, raw = parse_frc_text(source_text, validate=False)
        return tables, raw, source_text, "frc"
    elif suffix == ".prm":
        from upm.codecs._charmm_parser import parse_prm_text
        tables, raw = parse_prm_text(source_text)
        from upm.core.tables import normalize_tables
        tables = normalize_tables(tables)
        return tables, raw, source_text, "prm"
    else:
        raise ValueError(f"Unsupported extension: {suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a .frc or .prm file")
    parser.add_argument("--path", required=True, help="Path to .frc or .prm file")
    parser.add_argument("--name", required=True, help="Bundle name (e.g., cvff-interface-v1-5)")
    parser.add_argument("--version", default="v1.0", help="Bundle version")
    parser.add_argument("--author", default="Hendrik Heinz")
    parser.add_argument("--lab", default="Heinz Lab, CU Boulder")
    parser.add_argument("--date-created", default="")
    parser.add_argument("--doi", default=None)
    parser.add_argument("--materials", default="", help="Comma-separated materials")
    parser.add_argument("--parent-ff", default=None)
    parser.add_argument("--notes", default="")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()

    src_path = Path(args.path).resolve()
    if not src_path.exists():
        print(f"ERROR: File not found: {src_path}")
        sys.exit(1)

    data_dir = Path(args.data_dir).resolve() if args.data_dir else _REPO_ROOT / "src" / "iff_parameters" / "data"
    materials = [m.strip() for m in args.materials.split(",") if m.strip()]

    print(f"Ingesting: {src_path.name}")
    tables, raw_sections, source_text, fmt = _parse_file(src_path)
    print(f"  Format: {fmt}")
    for tname, df in sorted(tables.items()):
        print(f"  {tname}: {len(df)} rows")

    # Save bundle
    from upm.bundle.io import save_package

    root = data_dir / args.name / args.version
    units = {"length": "angstrom", "energy": "kcal/mol", "mass": "amu", "angle": "degree"}
    nonbonded = {"style": "A-B", "form": "12-6", "mixing": "geometric"} if fmt == "frc" else {"style": "eps-rmin", "form": "12-6", "mixing": "arithmetic"}

    save_package(root, name=args.name, version=args.version, tables=tables,
                 source_text=source_text, unknown_sections=raw_sections,
                 units=units, nonbonded=nonbonded)
    print(f"  Bundle saved: {root}")

    # Patch provenance
    from iff_parameters._provenance import Provenance, sha256_of_file

    prov = Provenance(
        author=args.author, lab=args.lab, date_created=args.date_created,
        publication_doi=args.doi, source_file=src_path.name,
        source_sha256=sha256_of_file(src_path), parent_ff=args.parent_ff,
        materials=materials, notes=args.notes,
    )
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["provenance"] = prov.to_dict()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Verify roundtrip
    from upm.bundle.io import load_package
    bundle = load_package(root)
    assert len(bundle.tables.get("atom_types", [])) > 0, "Roundtrip failed: no atom_types"
    print(f"  Roundtrip: PASS")
    print(f"\nDone. Bundle at: {root}")


if __name__ == "__main__":
    main()
