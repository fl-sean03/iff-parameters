"""Test search_by_material."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from upm.bundle.io import save_package
from upm.core.tables import normalize_tables
from iff_parameters._provenance import Provenance


def test_search_by_material(tmp_path: Path, monkeypatch) -> None:
    rows = [{"atom_type": "Au", "element": "Au", "mass_amu": 196.967,
             "vdw_style": "lj_ab_12_6", "lj_a": 100.0, "lj_b": 10.0, "notes": None}]
    tables = normalize_tables({"atom_types": pd.DataFrame(rows)})

    root = tmp_path / "metals" / "v1"
    save_package(root, name="metals", version="v1",
                 tables=tables, source_text="! test", unknown_sections=[])

    prov = Provenance(author="Test", materials=["Au", "Ag", "Cu"])
    m = json.loads((root / "manifest.json").read_text())
    m["provenance"] = prov.to_dict()
    (root / "manifest.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")

    import iff_parameters
    monkeypatch.setattr(iff_parameters, "get_data_dir", lambda: tmp_path)

    results = iff_parameters.search_by_material("Au")
    assert len(results) == 1
    assert "Au" in results[0]["materials"]

    assert len(iff_parameters.search_by_material("Nonexistent")) == 0
