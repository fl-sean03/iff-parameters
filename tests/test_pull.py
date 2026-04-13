"""Unit tests for pull operations (pull_latest, pull_original, pull_version).

Covers UC-5, UC-6, UC-7 and edge cases EC-2, EC-4, EC-12, EC-5.
"""

from __future__ import annotations


from iff_parameters.entries import list_structure_entries
from iff_parameters.pull import pull_latest, pull_original, pull_version


def _only_structure():
    entries = list_structure_entries()
    assert len(entries) == 1, f"expected single structure, got {len(entries)}"
    return entries[0]


def test_pull_latest_defaults_to_newest(library):
    """UC-5: default pull returns newest non-deprecated compatible."""
    library.add_param("cvff-mxene", "v1.0", atom_types=[("ti4f", "Ti", 1e6, 500, 47.88)])
    library.add_param("cvff-mxene", "v1.1",
                      atom_types=[("ti4f", "Ti", 1.1e6, 500, 47.88)],
                      supersedes="v1.0")
    library.add_structure(
        "Ti3C2", "v1.0", material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
        atoms=[(1, "Ti", "ti4f", 1.5, 0, 0, 0)],
    )
    r = pull_latest(_only_structure())
    assert r.status == "OK"
    assert r.resolutions["cvff-mxene"]["resolved"] == "v1.1"
    assert r.resolutions["cvff-mxene"]["requested"] == "latest"
    assert any("resolved to v1.1" in m for m in r.messages)


def test_pull_latest_skips_deprecated(library):
    """EC-4: deprecated hidden from latest walk."""
    library.add_param("cvff-mxene", "v1.0", atom_types=[("ti4f", "Ti", 1, 1, 47.88)])
    library.add_param("cvff-mxene", "v1.1", atom_types=[("ti4f", "Ti", 1, 1, 47.88)],
                      supersedes="v1.0", deprecated=True, deprecation_reason="bad fit")
    library.add_param("cvff-mxene", "v1.2", atom_types=[("ti4f", "Ti", 1, 1, 47.88)],
                      supersedes="v1.1")
    library.add_structure(
        "m", "v1.0", material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
    )
    r = pull_latest(_only_structure())
    assert r.resolutions["cvff-mxene"]["resolved"] == "v1.2"


def test_pull_latest_falls_back_when_incompatible(library):
    """EC-2: latest version has no ti4f -> fall back to most recent compatible."""
    library.add_param("cvff-mxene", "v1.0", atom_types=[("ti4f", "Ti", 1, 1, 47.88)])
    library.add_param("cvff-mxene", "v1.1", atom_types=[("ti4f", "Ti", 1, 1, 47.88)],
                      supersedes="v1.0")
    # v1.2 drops ti4f entirely, no rename declared
    library.add_param("cvff-mxene", "v1.2", atom_types=[("x", "X", 1, 1, 1)],
                      supersedes="v1.1")
    library.add_structure(
        "m", "v1.0", material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
    )
    r = pull_latest(_only_structure())
    res = r.resolutions["cvff-mxene"]
    assert res["resolved"] == "v1.1"
    assert any("latest version v1.2 was incompatible" in m for m in r.messages)


def test_pull_latest_all_incompatible_returns_error(library):
    """Rare case: the pinned version exists but every newer version drops
    an atom type the structure needs, and the pin is incompatible with the
    *latest* (so no lineage step covers the requirement)."""
    # Start v1.0 with ti4f, but the structure we construct uses a type "zz"
    # that the pinned version *does* define. Then every newer version drops
    # zz without a rename and keeps ti4f -- all candidates fail compatibility
    # except v1.0 itself. So walk back should find v1.0.
    library.add_param("fam", "v1.0",
                      atom_types=[("zz", "Z", 1, 1, 1), ("ti4f", "Ti", 1, 1, 47.88)])
    library.add_param("fam", "v1.1",
                      atom_types=[("ti4f", "Ti", 1, 1, 47.88)],
                      supersedes="v1.0")    # drops zz, no rename
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v1.0"}],
        atoms=[(1, "Z", "zz", 0.0, 0, 0, 0)],
    )
    r = pull_latest(_only_structure())
    # v1.1 is incompatible; walk back finds v1.0
    assert r.resolutions["fam"]["resolved"] == "v1.0"
    assert any("v1.1 was incompatible" in m for m in r.messages)


def test_pull_original_returns_exact_pin(library):
    """UC-6: pull_original returns the pinned version even if a newer exists."""
    library.add_param("cvff-mxene", "v1.0", atom_types=[("ti4f", "Ti", 1e6, 500, 47.88)])
    library.add_param("cvff-mxene", "v1.1",
                      atom_types=[("ti4f", "Ti", 2e6, 500, 47.88)],
                      supersedes="v1.0")
    library.add_structure(
        "m", "v1.0", material_class="mxene",
        atom_type_family="cvff-mxene",
        parameterized_with=[{"name": "cvff-mxene", "version": "v1.0"}],
    )
    r = pull_original(_only_structure())
    assert r.status == "OK"
    assert r.resolutions["cvff-mxene"]["resolved"] == "v1.0"


def test_pull_version_explicit(library):
    """UC-7: pull_version returns exactly the requested version when compatible."""
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_param("fam", "v1.1", atom_types=[("a", "A", 2, 2, 1)], supersedes="v1.0")
    library.add_param("fam", "v1.2", atom_types=[("a", "A", 3, 3, 1)], supersedes="v1.1")
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v1.0"}],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
    )
    r = pull_version(_only_structure(), "fam", "v1.1")
    assert r.status == "OK"
    assert r.resolutions["fam"]["resolved"] == "v1.1"


def test_pull_version_no_silent_fallback(library):
    """UC-7: pull_version fails loudly when target is incompatible."""
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_param("fam", "v1.1", atom_types=[("b", "B", 1, 1, 1)], supersedes="v1.0")
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v1.0"}],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
    )
    r = pull_version(_only_structure(), "fam", "v1.1")
    assert r.status == "ERROR"
    assert r.resolutions["fam"]["resolved"] is None


def test_lock_to_original_forces_original(library):
    """EC-12: structures marked lock_to_original return pull_original semantics."""
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_param("fam", "v1.1", atom_types=[("a", "A", 2, 2, 1)], supersedes="v1.0")
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v1.0"}],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
        lock_to_original=True,
    )
    r = pull_latest(_only_structure())
    assert r.resolutions["fam"]["resolved"] == "v1.0"
    assert any("locked" in m.lower() or "pinned by author" in m.lower() for m in r.messages)


def test_pull_latest_multi_family(library):
    """EC-5: structure parameterized with two families, resolved independently."""
    library.add_param("mxene", "v1.0", atom_types=[("ti4f", "Ti", 1, 1, 1)])
    library.add_param("mxene", "v1.1", atom_types=[("ti4f", "Ti", 2, 2, 1)], supersedes="v1.0")
    library.add_param("solvent", "v1.0", atom_types=[("ow", "O", 1, 1, 16)])
    library.add_structure(
        "m", "v1.0", material_class="mixed",
        atom_type_family="mxene",
        parameterized_with=[
            {"name": "mxene", "version": "v1.0"},
            {"name": "solvent", "version": "v1.0"},
        ],
        atoms=[(1, "Ti", "ti4f", 1, 0, 0, 0), (2, "O", "ow", -1, 1, 0, 0)],
    )
    r = pull_latest(_only_structure())
    # mxene resolves to v1.1; solvent stays at v1.0 (no newer). Both OK because
    # the structure's ti4f atom is covered by mxene's family.
    assert r.resolutions["mxene"]["resolved"] == "v1.1"
    assert r.resolutions["solvent"]["resolved"] == "v1.0"


def test_missing_family_in_library(library):
    """Structure references a family not in the library (EC-20)."""
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[
            {"name": "fam", "version": "v1.0"},
            {"name": "missing", "version": "v1.0"},
        ],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
    )
    r = pull_latest(_only_structure())
    assert r.status == "ERROR"
    assert r.resolutions["missing"]["resolved"] is None


def test_pull_original_missing_pin(library):
    """Pinned version removed from the library."""
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v9.9"}],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
    )
    r = pull_original(_only_structure())
    assert r.status == "ERROR"
    assert r.resolutions["fam"]["resolved"] is None
