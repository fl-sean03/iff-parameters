"""Unit tests for compatibility_check (and compose_renames).

Covers edge cases EC-1, EC-2, EC-3, EC-4, EC-14, EC-20 from USE_CASES.md.
"""

from __future__ import annotations

from iff_parameters.compat import compatibility_check, compose_renames
from iff_parameters.entries import index_family_versions


def test_same_version_pin_is_ok(library):
    """UC-6 base case: pulling original pin always resolves."""
    library.add_param(
        "cvff-mxene", "v1.0",
        atom_types=[("ti4f", "Ti", 1e6, 500.0, 47.88), ("o2", "O", 5e5, 300.0, 16.0)],
    )
    library.add_structure(
        "Ti3C2", "v1.0",
        material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        atoms=[(1, "Ti", "ti4f", 1.5, 0, 0, 0), (2, "O", "o2", -1.0, 1, 0, 0)],
    )

    from iff_parameters.entries import list_structure_entries
    structure = list_structure_entries()[0]
    result = compatibility_check(structure, "cvff-mxene", "v1.0")

    assert result.status == "OK"
    assert result.renames_applied == {}
    assert result.breaking_crossed is False
    assert result.missing == {}


def test_rename_auto_applied(library):
    """EC-1: ti4f renamed to ti4fh in v1.1; structure pinned to v1.0."""
    library.add_param(
        "cvff-mxene", "v1.0",
        atom_types=[("ti4f", "Ti", 1e6, 500.0, 47.88)],
    )
    library.add_param(
        "cvff-mxene", "v1.1",
        atom_types=[("ti4fh", "Ti", 1e6, 500.0, 47.88)],
        supersedes="v1.0",
        renames={"ti4f": "ti4fh"},
    )
    library.add_structure(
        "Ti3C2", "v1.0",
        material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        atoms=[(1, "Ti", "ti4f", 1.5, 0, 0, 0)],
    )

    from iff_parameters.entries import list_structure_entries
    structure = list_structure_entries()[0]
    result = compatibility_check(structure, "cvff-mxene", "v1.1")

    assert result.status == "OK"
    assert result.renames_applied == {"ti4f": "ti4fh"}
    assert "atom_types" not in result.missing


def test_missing_atom_type_is_error(library):
    """EC-2: type removed, no rename declared -> ERROR with missing list."""
    library.add_param(
        "cvff-mxene", "v1.0",
        atom_types=[("ti4f", "Ti", 1e6, 500.0, 47.88)],
    )
    library.add_param(
        "cvff-mxene", "v1.1",
        atom_types=[("c3a", "C", 1e5, 200.0, 12.01)],
        supersedes="v1.0",
    )
    library.add_structure(
        "Ti3C2", "v1.0",
        material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        atoms=[(1, "Ti", "ti4f", 1.5, 0, 0, 0)],
    )
    from iff_parameters.entries import list_structure_entries
    structure = list_structure_entries()[0]
    result = compatibility_check(structure, "cvff-mxene", "v1.1")
    assert result.status == "ERROR"
    assert result.missing.get("atom_types") == ["ti4f"]


def test_breaking_change_is_warning_when_keys_present(library):
    """EC-3: v2.0 declares breaking=True but keys still resolve -> WARNING."""
    library.add_param(
        "cvff-mxene", "v1.0",
        atom_types=[("ti4f", "Ti", 1e6, 500.0, 47.88)],
    )
    library.add_param(
        "cvff-mxene", "v2.0",
        atom_types=[("ti4f", "Ti", 1e6, 500.0, 47.88)],
        supersedes="v1.0",
        breaking=True,
    )
    library.add_structure(
        "Ti3C2", "v1.0",
        material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        atoms=[(1, "Ti", "ti4f", 1.5, 0, 0, 0)],
    )
    from iff_parameters.entries import list_structure_entries
    structure = list_structure_entries()[0]
    result = compatibility_check(structure, "cvff-mxene", "v2.0")
    assert result.status == "WARNING"
    assert result.breaking_crossed is True
    assert result.missing == {}


def test_rename_chain_composition_over_multiple_versions(library):
    """EC-14 partial: rename chain composed over v1.0 -> v1.1 -> v1.2."""
    library.add_param(
        "cvff-mxene", "v1.0",
        atom_types=[("a", "Ti", 1e6, 500.0, 47.88)],
    )
    library.add_param(
        "cvff-mxene", "v1.1",
        atom_types=[("b", "Ti", 1e6, 500.0, 47.88)],
        supersedes="v1.0",
        renames={"a": "b"},
    )
    library.add_param(
        "cvff-mxene", "v1.2",
        atom_types=[("c", "Ti", 1e6, 500.0, 47.88)],
        supersedes="v1.1",
        renames={"b": "c"},
    )
    library.add_structure(
        "model", "v1.0",
        material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        atoms=[(1, "Ti", "a", 1.0, 0, 0, 0)],
    )
    from iff_parameters.entries import list_structure_entries
    structure = list_structure_entries()[0]
    result = compatibility_check(structure, "cvff-mxene", "v1.2")
    assert result.status == "OK"
    # compose_renames tracks every rename in the chain; what matters is a -> c
    assert result.renames_applied["a"] == "c"


def test_rejects_wrong_family(library):
    """Structure not parameterized with target family -> ERROR."""
    library.add_param("cvff-other", "v1.0", atom_types=[("x", "X", 1.0, 1.0, 1.0)])
    library.add_param("cvff-mxene", "v1.0", atom_types=[("ti4f", "Ti", 1.0, 1.0, 1.0)])
    library.add_structure(
        "m", "v1.0",
        material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
    )
    from iff_parameters.entries import list_structure_entries
    structure = list_structure_entries()[0]
    result = compatibility_check(structure, "cvff-other", "v1.0")
    assert result.status == "ERROR"
    assert any("not parameterized with family" in m for m in result.messages)


def test_rejects_missing_target_entry(library):
    """Target family@version doesn't exist in the library."""
    library.add_param("cvff-mxene", "v1.0", atom_types=[("ti4f", "Ti", 1.0, 1.0, 1.0)])
    library.add_structure(
        "m", "v1.0",
        material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
    )
    from iff_parameters.entries import list_structure_entries
    structure = list_structure_entries()[0]
    result = compatibility_check(structure, "cvff-mxene", "v9.9")
    assert result.status == "ERROR"


def test_compose_renames_identity_when_no_renames(library):
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1.0, 1.0, 1.0)])
    library.add_param("fam", "v1.1", supersedes="v1.0", atom_types=[("a", "A", 1.0, 1.0, 1.0)])
    fv = index_family_versions()["fam"]
    assert compose_renames(fv, "v1.0", "v1.1") == {}
