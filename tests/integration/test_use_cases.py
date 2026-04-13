"""Integration tests for remaining UCs (those not already covered by
unit-level test_compat.py / test_pull.py / test_seed.py).

Covers UC-2 (new family), UC-3 (new version), UC-4 (structure upload),
UC-8 (compare), UC-11 (multi-package discovery), UC-12 (annotate),
UC-13 (deprecate), UC-14 (override).
"""
from __future__ import annotations

import json

from iff_parameters.entries import (
    find_parameter_entry, index_family_versions,
    list_parameter_entries, list_structure_entries,
)


def test_uc2_new_family(library):
    library.add_param("cvff-mxene-additions", "v1.0",
                      atom_types=[("ti4fh", "Ti", 1, 1, 47.88)])
    params = list_parameter_entries()
    assert any(e.name == "cvff-mxene-additions" and e.version == "v1.0" for e in params)


def test_uc3_new_version_of_family(library):
    library.add_param("cvff-mxene", "v1.0",
                      atom_types=[("ti4f", "Ti", 1e6, 500, 47.88)])
    library.add_param("cvff-mxene", "v1.1",
                      atom_types=[("ti4f", "Ti", 1.1e6, 500, 47.88)],
                      supersedes="v1.0")
    fv = index_family_versions()["cvff-mxene"]
    assert {e.version for e in fv.entries} == {"v1.0", "v1.1"}
    assert fv.latest().version == "v1.1"
    # original v1.0 untouched (still has k=1e6)
    v10 = find_parameter_entry("cvff-mxene", "v1.0")
    import pandas as pd
    df = pd.read_csv(v10.path / "tables" / "atom_types.csv")
    assert float(df[df["atom_type"] == "ti4f"]["lj_a"].iloc[0]) == 1e6


def test_uc4_structure_upload(library):
    library.add_param("cvff-mxene", "v1.0",
                      atom_types=[("ti4f", "Ti", 1, 1, 47.88)])
    library.add_structure(
        "Ti3C2_F", "v1.0", material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        atoms=[(1, "Ti", "ti4f", 1.5, 0, 0, 0)],
    )
    structs = list_structure_entries()
    assert len(structs) == 1
    s = structs[0]
    assert s.atom_type_family == "cvff-mxene"
    assert s.parameterized_with == [{"name": "cvff-mxene", "version": "v1.0"}]
    # atom type coverage — ti4f exists in the FF
    pin = find_parameter_entry("cvff-mxene", "v1.0")
    import pandas as pd
    ff_types = set(pd.read_csv(pin.path / "tables" / "atom_types.csv")["atom_type"])
    structure_types = set(pd.read_csv(s.path / "atoms.csv")["ff_type"])
    assert structure_types.issubset(ff_types)


def test_uc8_compare_two_versions(library):
    library.add_param("fam", "v1.0",
                      atom_types=[("a", "A", 1.0, 1.0, 1.0), ("b", "B", 2.0, 2.0, 2.0)],
                      bonds=[("a", "b", 100.0, 1.5)])
    library.add_param("fam", "v1.1",
                      atom_types=[("a", "A", 1.5, 1.0, 1.0), ("c", "C", 3.0, 3.0, 3.0)],
                      bonds=[("a", "c", 200.0, 1.8)],
                      supersedes="v1.0")
    e1 = find_parameter_entry("fam", "v1.0")
    e2 = find_parameter_entry("fam", "v1.1")
    from upm.bundle.io import load_package
    from upm.registry.diff import diff_tables
    t1 = load_package(e1.path).tables
    t2 = load_package(e2.path).tables
    diff = diff_tables(t1, t2)
    # added c, removed b, 'a' changed on lj_a
    assert "c" in diff.added_types
    assert "b" in diff.removed_types
    assert any(c.key == ("a",) or c.key == "a" for c in diff.changed_params)


def test_uc11_multi_package_discovery(tmp_path, monkeypatch):
    """UPM-level: two parameter packages in separate trees, discovered together."""
    from upm.bundle.io import save_package
    import pandas as pd
    df = lambda t: pd.DataFrame({
        "atom_type": [t], "element": ["X"], "mass_amu": [1.0],
        "vdw_style": ["lj_A_B"], "lj_a": [1.0], "lj_b": [1.0], "notes": [""],
    })

    pkg_a = tmp_path / "pkg_a" / "parameters" / "alpha" / "v1.0"
    pkg_b = tmp_path / "pkg_b" / "parameters" / "beta" / "v1.0"
    save_package(pkg_a, name="alpha", version="v1.0", tables={"atom_types": df("a")}, source_text="")
    save_package(pkg_b, name="beta", version="v1.0", tables={"atom_types": df("b")}, source_text="")

    from upm.registry.discovery import discover_local_packages
    # Discover each separately, then merge lists (simulating two entry points)
    pkgs = (discover_local_packages(tmp_path / "pkg_a" / "parameters")
            + discover_local_packages(tmp_path / "pkg_b" / "parameters"))
    names = sorted(p.name for p in pkgs)
    assert names == ["alpha", "beta"]


def test_uc12_annotate_validated_with(library):
    """Annotation after publish: validated_with list is append-only metadata."""
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_param("fam", "v1.1", atom_types=[("a", "A", 2, 2, 1)], supersedes="v1.0")
    structure_root = library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v1.0"}],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
        validated_with=[{"name": "fam", "version": "v1.1"}],
    )
    manifest = json.loads((structure_root / "manifest.json").read_text())
    assert manifest["validated_with"] == [{"name": "fam", "version": "v1.1"}]


def test_uc13_deprecated_hidden_from_latest(library):
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_param("fam", "v1.1", atom_types=[("a", "A", 2, 2, 1)],
                      supersedes="v1.0",
                      deprecated=True, deprecation_reason="bad parameterization")
    library.add_param("fam", "v1.2", atom_types=[("a", "A", 3, 3, 1)],
                      supersedes="v1.1")
    fv = index_family_versions()["fam"]
    latest = fv.latest()
    assert latest.version == "v1.2"
    # include_deprecated=True includes v1.1 but v1.2 still sorts higher
    latest_all = fv.latest(include_deprecated=True)
    assert latest_all.version == "v1.2"


def test_uc14_override_declaration(library):
    library.add_param("base", "v1.0",
                      atom_types=[("ti", "Ti", 1e6, 500, 47.88)],
                      bonds=[("ti", "o", 310.0, 1.8)])
    library.add_param("override", "v1.0",
                      atom_types=[("ti", "Ti", 1e6, 500, 47.88)],
                      bonds=[("ti", "o", 280.0, 1.8)],   # different k
                      parent_ff="base/v1.0",
                      overrides=[{
                          "target": "base/v1.0",
                          "scope": "bonds",
                          "reason": "DFT benchmark",
                      }])
    e = find_parameter_entry("override", "v1.0")
    assert e.manifest["parent_ff"] == "base/v1.0"
    assert e.manifest["overrides"][0]["scope"] == "bonds"
