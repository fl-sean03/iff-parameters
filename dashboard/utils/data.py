"""Data loading and caching for the IFF dashboard."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Resolve repo root: dashboard/utils/data.py → dashboard/utils → dashboard → repo root
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parent.parent.parent  # utils → dashboard → repo root
_DATA_DIR = _REPO_ROOT / "src" / "iff_parameters" / "data"

# Fallback: scan upward for src/iff_parameters/data if direct path fails
if not _DATA_DIR.is_dir():
    for parent in _THIS_FILE.parents:
        candidate = parent / "src" / "iff_parameters" / "data"
        if candidate.is_dir():
            _DATA_DIR = candidate
            _REPO_ROOT = parent
            break


def get_data_dir() -> str:
    """Get the path to the data directory."""
    return str(_DATA_DIR)


@st.cache_data(ttl=60)
def list_bundles() -> list[dict[str, Any]]:
    """List all available bundles by scanning manifest files."""
    data_dir = Path(get_data_dir())
    results: list[dict[str, Any]] = []
    if not data_dir.is_dir():
        return results

    for manifest_path in sorted(data_dir.rglob("manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            provenance = manifest.get("provenance", {})
            source_file = provenance.get("source_file", "")
            fmt = "cvff" if source_file.endswith(".frc") else "charmm" if source_file.endswith(".prm") else "unknown"
            results.append({
                "name": manifest.get("name", "unknown"),
                "version": manifest.get("version", "unknown"),
                "materials": provenance.get("materials", []),
                "format": fmt,
                "source_file": source_file,
                "author": provenance.get("author", ""),
                "doi": provenance.get("publication_doi"),
                "path": str(manifest_path.parent),
            })
        except Exception:
            continue
    return results


@st.cache_data(ttl=3600)
def load_bundle_tables(bundle_path: str) -> dict[str, pd.DataFrame]:
    """Load all CSV tables from a bundle directory."""
    tables_dir = Path(bundle_path) / "tables"
    tables: dict[str, pd.DataFrame] = {}
    if not tables_dir.is_dir():
        return tables
    for csv_file in sorted(tables_dir.glob("*.csv")):
        name = csv_file.stem
        tables[name] = pd.read_csv(csv_file)
    return tables


@st.cache_data(ttl=3600)
def load_manifest(bundle_path: str) -> dict[str, Any]:
    mp = Path(bundle_path) / "manifest.json"
    return json.loads(mp.read_text(encoding="utf-8"))


@st.cache_data(ttl=3600)
def get_all_atom_types() -> pd.DataFrame:
    """Aggregate atom types across all bundles."""
    rows = []
    for entry in list_bundles():
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


@st.cache_data(ttl=60)
def get_bundle_stats() -> dict[str, Any]:
    """Compute aggregate statistics across all bundles."""
    bundles = list_bundles()
    total_atoms = 0
    total_bonds = 0
    total_angles = 0
    total_torsions = 0
    total_oop = 0
    all_materials: set[str] = set()

    for entry in bundles:
        tables = load_bundle_tables(entry["path"])
        total_atoms += len(tables.get("atom_types", []))
        total_bonds += len(tables.get("bonds", []))
        total_angles += len(tables.get("angles", []))
        total_torsions += len(tables.get("torsions", []))
        total_oop += len(tables.get("out_of_plane", []))
        all_materials.update(entry.get("materials", []))

    return {
        "n_bundles": len(bundles),
        "total_atoms": total_atoms,
        "total_bonds": total_bonds,
        "total_angles": total_angles,
        "total_torsions": total_torsions,
        "total_oop": total_oop,
        "n_materials": len(all_materials),
        "materials": sorted(all_materials),
    }
