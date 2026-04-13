"""Data loading + caching for the IFF dashboard (v0.2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Resolve repo root: dashboard/utils/data.py → dashboard/utils → dashboard → repo root
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "src" / "iff_parameters" / "data"

if not _DATA_DIR.is_dir():
    for parent in _THIS_FILE.parents:
        candidate = parent / "src" / "iff_parameters" / "data"
        if candidate.is_dir():
            _DATA_DIR = candidate
            _REPO_ROOT = parent
            break

# Make the iff_parameters package importable (local dev)
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def get_data_dir() -> str:
    return str(_DATA_DIR)


_ARCHIVE = "archive"


# ---------------------------------------------------------------------------
# Parameter entries (FFs)

@st.cache_data(ttl=60)
def list_parameter_entries() -> list[dict[str, Any]]:
    """List live parameter entries."""
    data_dir = Path(get_data_dir()) / "parameters"
    out: list[dict[str, Any]] = []
    if not data_dir.is_dir():
        return out
    for manifest_path in sorted(data_dir.rglob("manifest.json")):
        if _ARCHIVE in manifest_path.parts:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if manifest.get("type", "parameters") != "parameters":
            continue
        provenance = manifest.get("provenance", {})
        source_file = provenance.get("source_file", "")
        fmt = ("cvff" if source_file.endswith(".frc")
               else "charmm" if source_file.endswith(".prm")
               else "unknown")
        out.append({
            "name": manifest.get("name", "unknown"),
            "version": manifest.get("version", "unknown"),
            "ref": f"{manifest.get('name')}@{manifest.get('version')}",
            "materials": provenance.get("materials", []),
            "format": fmt,
            "source_file": source_file,
            "author": provenance.get("author", ""),
            "doi": provenance.get("publication_doi"),
            "supersedes": manifest.get("supersedes"),
            "deprecated": manifest.get("deprecated", False),
            "partial_roundtrip": manifest.get("partial_roundtrip", False),
            "path": str(manifest_path.parent),
        })
    return out


# Back-compat alias so legacy pages keep working while we migrate.
@st.cache_data(ttl=60)
def list_bundles() -> list[dict[str, Any]]:
    return list_parameter_entries()


@st.cache_data(ttl=3600)
def load_bundle_tables(bundle_path: str) -> dict[str, pd.DataFrame]:
    tables_dir = Path(bundle_path) / "tables"
    tables: dict[str, pd.DataFrame] = {}
    if not tables_dir.is_dir():
        return tables
    for csv_file in sorted(tables_dir.glob("*.csv")):
        tables[csv_file.stem] = pd.read_csv(csv_file)
    return tables


@st.cache_data(ttl=3600)
def load_manifest(bundle_path: str) -> dict[str, Any]:
    return json.loads((Path(bundle_path) / "manifest.json").read_text(encoding="utf-8"))


@st.cache_data(ttl=3600)
def get_all_atom_types() -> pd.DataFrame:
    rows = []
    for entry in list_parameter_entries():
        tables = load_bundle_tables(entry["path"])
        if "atom_types" not in tables:
            continue
        df = tables["atom_types"].copy()
        df["bundle"] = entry["name"]
        df["version"] = entry["version"]
        df["format"] = entry["format"]
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Structure entries

@st.cache_data(ttl=60)
def list_structure_entries() -> list[dict[str, Any]]:
    data_dir = Path(get_data_dir()) / "structures"
    out: list[dict[str, Any]] = []
    if not data_dir.is_dir():
        return out
    for manifest_path in sorted(data_dir.rglob("manifest.json")):
        if _ARCHIVE in manifest_path.parts:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if manifest.get("type") != "structure":
            continue
        provenance = manifest.get("provenance", {})
        # Material class = the directory right under "structures/"
        parts = manifest_path.relative_to(data_dir).parts
        material_class = parts[0] if parts else "unknown"
        out.append({
            "name": manifest.get("name", "unknown"),
            "version": manifest.get("version", "unknown"),
            "ref": f"{manifest.get('name')}@{manifest.get('version')}",
            "material_class": material_class,
            "materials": provenance.get("materials", []),
            "atom_type_family": manifest.get("atom_type_family"),
            "parameterized_with": manifest.get("parameterized_with", []),
            "charges_source": manifest.get("charges_source", "structure"),
            "lock_to_original": manifest.get("lock_to_original", False),
            "validated_with": manifest.get("validated_with", []),
            "n_atoms": manifest.get("atoms_csv", {}).get("rows", 0),
            "deprecated": manifest.get("deprecated", False),
            "path": str(manifest_path.parent),
        })
    return out


@st.cache_data(ttl=3600)
def load_structure_atoms(structure_path: str) -> pd.DataFrame:
    atoms_csv = Path(structure_path) / "atoms.csv"
    if not atoms_csv.is_file():
        return pd.DataFrame()
    return pd.read_csv(atoms_csv)


@st.cache_data(ttl=3600)
def load_structure_geometry_text(structure_path: str) -> str:
    for ext in ("car", "mdf", "pdb", "cif", "xyz"):
        p = Path(structure_path) / "geometry" / f"source.{ext}"
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return ""


# ---------------------------------------------------------------------------
# Aggregate stats (used by home page + coverage)

@st.cache_data(ttl=60)
def get_library_stats() -> dict[str, Any]:
    params = list_parameter_entries()
    structs = list_structure_entries()
    total_atoms = 0
    total_bonds = 0
    total_angles = 0
    total_torsions = 0
    total_oop = 0
    all_materials: set[str] = set()

    for entry in params:
        tables = load_bundle_tables(entry["path"])
        total_atoms += len(tables.get("atom_types", []))
        total_bonds += len(tables.get("bonds", []))
        total_angles += len(tables.get("angles", []))
        total_torsions += len(tables.get("torsions", []))
        total_oop += len(tables.get("out_of_plane", []))
        all_materials.update(entry.get("materials", []))
    for entry in structs:
        all_materials.update(entry.get("materials", []))
        all_materials.add(entry.get("material_class", ""))
    all_materials.discard("")

    return {
        "n_parameter_entries": len(params),
        "n_structure_entries": len(structs),
        "n_structure_atoms_total": sum(e["n_atoms"] for e in structs),
        "total_atom_types": total_atoms,
        "total_bonds": total_bonds,
        "total_angles": total_angles,
        "total_torsions": total_torsions,
        "total_oop": total_oop,
        "n_materials": len(all_materials),
        "materials": sorted(all_materials),
    }


# Back-compat alias.
@st.cache_data(ttl=60)
def get_bundle_stats() -> dict[str, Any]:
    s = get_library_stats()
    return {
        "n_bundles": s["n_parameter_entries"],
        "total_atoms": s["total_atom_types"],
        "total_bonds": s["total_bonds"],
        "total_angles": s["total_angles"],
        "total_torsions": s["total_torsions"],
        "total_oop": s["total_oop"],
        "n_materials": s["n_materials"],
        "materials": s["materials"],
    }
