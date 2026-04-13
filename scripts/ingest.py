#!/usr/bin/env python3
"""Ingest a single .frc or .prm file into a versioned UPM bundle.

Automatically compares against all existing bundles to detect
near-duplicates and suggest version bumps vs new bundles.

Usage:
    python scripts/ingest.py \
        --path my_forcefield.frc \
        --name my-ff \
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


def _compare_against_existing(
    new_tables: dict, data_dir: Path,
) -> list[dict]:
    """Compare incoming tables against all existing bundles.

    Returns list of similarity reports sorted by overlap (highest first).
    Each report: {name, version, path, overlap_pct, added, removed, changed}
    """
    from upm.bundle.io import load_package
    from upm.registry.diff import diff_tables

    if "atom_types" not in new_tables:
        return []

    new_types = set(new_tables["atom_types"]["atom_type"].tolist())
    if not new_types:
        return []

    reports = []
    for manifest_path in sorted(data_dir.rglob("manifest.json")):
        try:
            bundle = load_package(manifest_path.parent)
            if "atom_types" not in bundle.tables:
                continue

            existing_types = set(bundle.tables["atom_types"]["atom_type"].tolist())
            if not existing_types:
                continue

            # Compute overlap
            common = new_types & existing_types
            union = new_types | existing_types
            overlap_pct = len(common) / len(union) * 100 if union else 0

            # Only report if >50% overlap
            if overlap_pct < 50:
                continue

            # Get detailed diff
            diff = diff_tables(bundle.tables, new_tables)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            reports.append({
                "name": manifest.get("name", "unknown"),
                "version": manifest.get("version", "unknown"),
                "path": str(manifest_path.parent),
                "overlap_pct": round(overlap_pct, 1),
                "common_types": len(common),
                "total_new": len(new_types),
                "total_existing": len(existing_types),
                "added_types": len(diff.added_types),
                "removed_types": len(diff.removed_types),
                "changed_params": len(diff.changed_params),
                "added_list": diff.added_types[:10],
                "changed_list": [str(c) for c in diff.changed_params[:5]],
            })

        except Exception:
            continue

    reports.sort(key=lambda r: -r["overlap_pct"])
    return reports


def _print_similarity_report(reports: list[dict]) -> None:
    """Print similarity analysis against existing bundles."""
    if not reports:
        print("\n  Similarity: No existing bundles with >50% atom type overlap.")
        return

    print(f"\n  Similarity Analysis ({len(reports)} similar bundle(s) found):")
    print(f"  {'─' * 70}")

    for r in reports[:5]:  # Top 5
        print(f"  {r['name']}@{r['version']}: {r['overlap_pct']}% overlap")
        print(f"    Common: {r['common_types']} types | "
              f"Added: +{r['added_types']} | "
              f"Removed: -{r['removed_types']} | "
              f"Changed: ~{r['changed_params']}")

        if r["added_list"]:
            print(f"    New types: {', '.join(r['added_list'][:8])}"
                  f"{'...' if len(r['added_list']) > 8 else ''}")
        if r["changed_list"]:
            for c in r["changed_list"][:3]:
                print(f"    Changed: {c}")

        # Recommendation
        if r["overlap_pct"] > 95 and r["added_types"] == 0:
            print("    → RECOMMENDATION: This looks like a parameter update.")
            print(f"      Consider: --name {r['name']} --version v{_next_version(r['version'])}")
        elif r["overlap_pct"] > 80:
            print(f"    → RECOMMENDATION: This extends {r['name']}.")
            print(f"      Consider: --parent-ff {r['name']}")

        print()


def _next_version(current: str) -> str:
    """Suggest next version: v1.0 -> 2.0, v2.0 -> 3.0."""
    stripped = current.lstrip("v")
    try:
        major = int(stripped.split(".")[0])
        return f"{major + 1}.0"
    except (ValueError, IndexError):
        return "2.0"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a .frc or .prm file into a versioned UPM bundle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # New force field
    python scripts/ingest.py --path new_ff.frc --name my-ff --version v1.0

    # Updated version of existing bundle
    python scripts/ingest.py --path optimized.frc --name cvff-iff-metal-oxides-v2 --version v2.0

    # With full provenance
    python scripts/ingest.py --path ff.frc --name my-ff --version v1.0 \\
        --author "Sean Flores" --materials "Au,SiO2" --doi "10.1234/example"
""",
    )
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
    parser.add_argument("--skip-similarity", action="store_true",
                        help="Skip similarity check against existing bundles")
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

    # Similarity check against existing bundles
    if not args.skip_similarity:
        reports = _compare_against_existing(tables, data_dir)
        _print_similarity_report(reports)

    # Save bundle
    from upm.bundle.io import save_package

    root = data_dir / args.name / args.version
    units = {"length": "angstrom", "energy": "kcal/mol", "mass": "amu", "angle": "degree"}
    nonbonded = ({"style": "A-B", "form": "12-6", "mixing": "geometric"} if fmt == "frc"
                 else {"style": "eps-rmin", "form": "12-6", "mixing": "arithmetic"})

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
    print("  Roundtrip: PASS")
    print(f"\nDone. Bundle at: {root}")


if __name__ == "__main__":
    main()
