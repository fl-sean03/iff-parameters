"""Seed the library with structure entries from INTERFACE_FF_1_5/MODEL_DATABASE.

For every .car file under canonical_sources/INTERFACE_FF_1_5/MODEL_DATABASE/*,
parse atoms via USM, detect which seeded FF family covers all its atom types,
and write a structure entry at
  data/structures/<material_class>/<model_name>/v1.0/

If a .mdf sibling exists, it is copied alongside under geometry/ but not
parsed into topology yet (topology extraction is deferred; the geometry file
is the source of truth for atom types + charges).

Idempotent: running twice leaves the same bytes on disk. Use --force to
overwrite.

Logs to data/structures/_seed_log.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / "canonical_sources" / "INTERFACE_FF_1_5" / "MODEL_DATABASE"
DATA_DIR = REPO_ROOT / "src" / "iff_parameters" / "data"

# Families to consider, in preference order. First that covers every atom type wins.
FAMILY_PREFERENCE = ("cvff-interface", "pcff-interface", "charmm27-interface")
FAMILY_VERSION = "v1.5"

STRUCTURE_VERSION = "v1.0"
MATERIAL_CLASS_MAP = {
    "SILICA": "silica",
    "METALS": "metals",
    "CEMENT_MINERALS": "cement",
    "CLAY_MINERALS": "clay",
    "HYDROXYAPATITE": "hydroxyapatite",
    "CA_SULFATE": "ca-sulfate",
    "PEO": "peo",
}


@dataclass
class StructureSeed:
    material_class: str
    model_name: str
    source_file: str
    detected_family: str
    n_atoms: int
    path: str


@dataclass
class SeedRun:
    seeded_utc: str
    n_ingested: int
    n_skipped: int
    n_failed: int
    results: list[StructureSeed] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    out = name.strip().replace(" ", "_").replace("+", "-").replace(".", "_")
    return out


def _load_family_atom_types() -> dict[str, set[str]]:
    """Return {family_name: {atom_type, ...}} for each seeded FF family."""
    out: dict[str, set[str]] = {}
    for family in FAMILY_PREFERENCE:
        root = DATA_DIR / "parameters" / family / FAMILY_VERSION
        if not root.is_dir():
            print(f"WARNING: family {family}@{FAMILY_VERSION} not seeded — skipping", file=sys.stderr)
            continue
        from upm.bundle.io import load_package
        bundle = load_package(root)
        at = bundle.tables.get("atom_types")
        if at is None:
            continue
        out[family] = set(at["atom_type"].astype(str).tolist())
    return out


def _detect_family(structure_types: set[str], family_types: dict[str, set[str]]) -> str | None:
    """Return the first family (in preference order) that covers every type, else None."""
    for family in FAMILY_PREFERENCE:
        if family not in family_types:
            continue
        if structure_types.issubset(family_types[family]):
            return family
    return None


def seed_one_car(
    car_path: Path,
    material_class: str,
    family_types: dict[str, set[str]],
    *,
    force: bool = False,
) -> StructureSeed | None:
    from iff_parameters.car_parser import load_car_atoms
    atoms_df = load_car_atoms(car_path)
    if "ff_type" not in atoms_df.columns or atoms_df["ff_type"].isna().all():
        raise ValueError("no ff_type column in parsed CAR")

    # collect types (drop NaN / empty strings)
    types = set(
        s for s in atoms_df["ff_type"].astype(str).tolist()
        if s and s != "nan"
    )
    family = _detect_family(types, family_types)
    if family is None:
        raise ValueError(
            f"no seeded FF covers atom types {sorted(types)}; "
            f"tried {list(family_types)}"
        )

    model_name = _slugify(car_path.stem)
    target_root = DATA_DIR / "structures" / material_class / model_name / STRUCTURE_VERSION
    if target_root.exists():
        if not force:
            return None
        shutil.rmtree(target_root)

    # atoms_df already in canonical format from load_car_atoms
    # Copy .mdf companion alongside geometry/ if present (not parsed into topology yet)
    mdf_path = car_path.with_suffix(".mdf")
    geometry_text = car_path.read_text(encoding="utf-8", errors="replace")

    provenance = {
        "author": "Hendrik Heinz",
        "lab": "Heinz Lab, CU Boulder",
        "date_created": "2014-04-14",
        "source_file": car_path.name,
        "source_sha256": "",  # filled by save_structure via sha256 on geometry file
        "materials": [material_class],
        "notes": f"Pre-parameterized structure from INTERFACE_FF_1_5/MODEL_DATABASE/{car_path.parent.name}",
        "mdf_companion": mdf_path.name if mdf_path.is_file() else None,
        "ingested_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }

    from upm.bundle.io import save_structure
    save_structure(
        target_root,
        name=model_name, version=STRUCTURE_VERSION,
        atoms_df=atoms_df,
        geometry_text=geometry_text,
        geometry_format="car",
        atom_type_family=family,
        parameterized_with=[{"name": family, "version": FAMILY_VERSION}],
        provenance=provenance,
    )

    # Copy the .mdf file alongside (as a non-canonical companion) for reference.
    # Not added to manifest sources; it's an informational artifact.
    if mdf_path.is_file():
        (target_root / "geometry" / "source.mdf").write_text(
            mdf_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )

    return StructureSeed(
        material_class=material_class,
        model_name=model_name,
        source_file=car_path.name,
        detected_family=family,
        n_atoms=len(atoms_df),
        path=str(target_root.relative_to(REPO_ROOT)),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="overwrite existing entries")
    ap.add_argument("--class", dest="classes", action="append",
                    help="only seed these material classes (repeatable)")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N structures (for smoke testing)")
    args = ap.parse_args()

    if not CANONICAL_DIR.is_dir():
        print(f"ERROR: canonical MODEL_DATABASE not found at {CANONICAL_DIR}", file=sys.stderr)
        return 2

    family_types = _load_family_atom_types()
    if not family_types:
        print("ERROR: no seeded FF families found — run seed_from_interface_ff15_parameters.py first",
              file=sys.stderr)
        return 2

    (DATA_DIR / "structures").mkdir(parents=True, exist_ok=True)

    print(f"Scanning {CANONICAL_DIR}")
    print(f"Families available: {list(family_types.keys())}")
    print(f"Target: {DATA_DIR / 'structures'}")
    print()

    n_ingested = 0
    n_skipped = 0
    n_failed = 0
    results: list[StructureSeed] = []
    failures: list[dict] = []

    for src_class_dir in sorted(CANONICAL_DIR.iterdir()):
        if not src_class_dir.is_dir():
            continue
        material_class = MATERIAL_CLASS_MAP.get(src_class_dir.name, src_class_dir.name.lower())
        if args.classes and material_class not in args.classes:
            continue
        print(f"\n[{material_class}]")
        for car_path in sorted(src_class_dir.glob("*.car")):
            if args.limit is not None and n_ingested >= args.limit:
                break
            try:
                result = seed_one_car(car_path, material_class, family_types, force=args.force)
                if result is None:
                    n_skipped += 1
                    print(f"  skip  {car_path.name} (already exists)")
                else:
                    n_ingested += 1
                    results.append(result)
                    print(f"  ok    {car_path.name}  -> {result.detected_family}, "
                          f"{result.n_atoms} atoms")
            except Exception as e:
                n_failed += 1
                failures.append({
                    "source_file": str(car_path.relative_to(REPO_ROOT)),
                    "error": f"{type(e).__name__}: {e}",
                })
                print(f"  FAIL  {car_path.name}: {e}")

    run = SeedRun(
        seeded_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        n_ingested=n_ingested,
        n_skipped=n_skipped,
        n_failed=n_failed,
        results=results,
        failures=failures,
    )
    log_path = DATA_DIR / "structures" / "_seed_log.json"
    log_path.write_text(json.dumps({
        "seeded_utc": run.seeded_utc,
        "n_ingested": run.n_ingested,
        "n_skipped": run.n_skipped,
        "n_failed": run.n_failed,
        "results": [asdict(r) for r in run.results],
        "failures": run.failures,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print(f"ingested: {n_ingested}  skipped: {n_skipped}  failed: {n_failed}")
    print(f"log: {log_path.relative_to(REPO_ROOT)}")
    return 1 if n_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
