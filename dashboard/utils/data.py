"""Data loading and caching for the IFF dashboard."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600)
def get_data_dir() -> str:
    from iff_parameters import get_data_dir as _get
    return str(_get())


@st.cache_data(ttl=3600)
def list_bundles() -> list[dict[str, Any]]:
    from iff_parameters import list_available
    return list_available()


@st.cache_data(ttl=3600)
def load_bundle_tables(bundle_path: str) -> dict[str, pd.DataFrame]:
    from upm.bundle.io import load_package
    bundle = load_package(Path(bundle_path))
    return bundle.tables


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


@st.cache_data(ttl=3600)
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
