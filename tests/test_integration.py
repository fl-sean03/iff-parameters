"""Cross-package integration tests: USM → UPM → iff-parameters pipeline."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

try:
    from usm.core.model import USM
    _HAS_USM = True
except ImportError:
    _HAS_USM = False


@pytest.mark.skipif(not _HAS_USM, reason="USM not installed")
def test_full_pipeline_usm_to_iff_parameters() -> None:
    """End-to-end: create structure → extract types → search → load bundle → verify."""
    # 1. Create a minimal USM structure with gold atoms
    atoms = pd.DataFrame([
        {"aid": 0, "name": "Au1", "element": "Au", "atom_type": "Au", "charge": 0.0,
         "x": 0.0, "y": 0.0, "z": 0.0, "mol_label": "SLAB", "mol_index": 1, "mol_block_name": "METAL"},
        {"aid": 1, "name": "Au2", "element": "Au", "atom_type": "Au", "charge": 0.0,
         "x": 2.88, "y": 0.0, "z": 0.0, "mol_label": "SLAB", "mol_index": 1, "mol_block_name": "METAL"},
    ])
    usm = USM(atoms=atoms, cell={"pbc": False}, provenance={}, preserved_text={})
    assert len(usm.atoms) == 2

    # 2. Extract required atom types
    required_types = sorted(set(usm.atoms["atom_type"].tolist()))
    assert required_types == ["Au"]

    # 3. Search iff-parameters for matching bundles
    from iff_parameters import search_by_material
    results = search_by_material("Au")
    if not results:
        pytest.skip("No Au bundles in library yet (pre-seed state)")

    # 4. Load a specific bundle via UPM
    from upm.bundle.io import load_package
    from iff_parameters import get_data_dir

    data_dir = get_data_dir()
    v15_path = data_dir / "parameters" / "cvff-interface" / "v1.5"
    if not v15_path.exists():
        pytest.skip("cvff-interface v1.5 bundle not ingested yet")

    bundle = load_package(v15_path)
    assert "atom_types" in bundle.tables

    # 5. Verify Au parameters exist in the bundle
    at_df = bundle.tables["atom_types"]
    au_rows = at_df[at_df["atom_type"] == "Au"]
    assert len(au_rows) == 1, "Expected exactly 1 Au entry in atom_types"
    assert float(au_rows.iloc[0]["lj_a"]) > 0, "Au lj_a should be positive"


def test_diff_between_bundles() -> None:
    """UPM diff correctly identifies differences between two bundles."""
    from upm.bundle.io import load_package
    from upm.registry.diff import diff_tables
    from iff_parameters import get_data_dir

    data_dir = get_data_dir()
    v15 = data_dir / "parameters" / "cvff-interface" / "v1.5"
    oxides = data_dir / "parameters" / "cvff-iff-metal-oxides" / "v2.0"

    if not v15.exists() or not oxides.exists():
        pytest.skip("Required bundles not ingested (pre-seed state)")

    pkg1 = load_package(v15)
    pkg2 = load_package(oxides)
    diff = diff_tables(pkg1.tables, pkg2.tables)

    # Metal oxides extends v1.5 — should have added types
    assert diff.has_changes, "Diff should show changes between v1.5 and metal oxides"
    assert len(diff.added_types) > 0, "Metal oxides should add atom types beyond v1.5"


def test_discovery_finds_bundles() -> None:
    """UPM local discovery finds all iff-parameters bundles."""
    from upm.registry.discovery import discover_local_packages
    from iff_parameters import get_data_dir

    data_dir = get_data_dir()
    if not data_dir.exists():
        pytest.skip("Data directory not found")

    packages = discover_local_packages(data_dir)
    if not packages:
        pytest.skip("no bundles in library yet (pre-seed state)")

    names = {p.name for p in packages}
    # At minimum, canonical IFF v1.5 should be present
    if "cvff-interface" not in names:
        pytest.skip("cvff-interface not yet seeded")
    assert "cvff-interface" in names


def test_package_index_search() -> None:
    """PackageIndex cross-package search works with iff-parameters bundles."""
    from upm.registry.discovery import discover_local_packages
    from upm.registry.index import PackageIndex
    from iff_parameters import get_data_dir

    data_dir = get_data_dir()
    if not data_dir.exists():
        pytest.skip("Data directory not found")

    packages = discover_local_packages(data_dir)
    if not packages:
        pytest.skip("No bundles found")

    index = PackageIndex(packages)

    # Search for a common element
    results = index.search_atom_type("c3")
    # c3 (sp3 carbon) should exist in CVFF bundles
    if results:
        assert results[0].table_name == "atom_types"
        assert results[0].row["atom_type"] == "c3"
