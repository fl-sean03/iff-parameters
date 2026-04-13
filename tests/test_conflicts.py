"""Unit tests for iff_parameters.conflicts (upload-time collision detection)."""

from __future__ import annotations

import pandas as pd

from iff_parameters.conflicts import count_conflicts, detect_collisions


def _at_df(rows: list[tuple[str, str, float, float, float]]) -> pd.DataFrame:
    """(atom_type, element, mass, lj_a, lj_b)"""
    return pd.DataFrame({
        "atom_type": [r[0] for r in rows],
        "element": [r[1] for r in rows],
        "mass_amu": [r[2] for r in rows],
        "vdw_style": ["lj_A_B"] * len(rows),
        "lj_a": [r[3] for r in rows],
        "lj_b": [r[4] for r in rows],
        "notes": [""] * len(rows),
    })


def _bonds_df(rows: list[tuple[str, str, float, float]]) -> pd.DataFrame:
    return pd.DataFrame({
        "t1": [r[0] for r in rows],
        "t2": [r[1] for r in rows],
        "style": ["harm"] * len(rows),
        "k": [r[2] for r in rows],
        "r0": [r[3] for r in rows],
        "source": [""] * len(rows),
    })


def _make_existing(name: str, version: str, atom_rows, bond_rows):
    """Return (entry_dict, loader_callback) pair for detect_collisions."""
    tables = {}
    if atom_rows is not None:
        tables["atom_types"] = _at_df(atom_rows)
    if bond_rows is not None:
        tables["bonds"] = _bonds_df(bond_rows)
    entry = {"ref": f"{name}@{version}", "path": f"/fake/{name}/{version}"}
    return entry, tables


def test_no_collisions_when_entries_disjoint():
    new_tables = {"atom_types": _at_df([("a", "A", 1.0, 10.0, 1.0)])}
    entry, tables = _make_existing("other", "v1.0",
                                    atom_rows=[("z", "Z", 9.0, 9.0, 9.0)], bond_rows=None)
    coll = detect_collisions(new_tables, [entry], lambda _p: tables)
    assert coll == []
    assert count_conflicts(coll) == (0, 0)


def test_harmless_duplicate_not_flagged_as_conflict():
    new_tables = {"atom_types": _at_df([("ti4f", "Ti", 47.88, 1e6, 500.0)])}
    entry, tables = _make_existing("base", "v1.0",
                                    atom_rows=[("ti4f", "Ti", 47.88, 1e6, 500.0)], bond_rows=None)
    coll = detect_collisions(new_tables, [entry], lambda _p: tables)
    assert len(coll) == 1
    assert coll[0].status == "duplicate"
    assert coll[0].disagrees_on == []
    assert count_conflicts(coll) == (0, 1)


def test_value_disagreement_flagged_as_conflict():
    new_tables = {"atom_types": _at_df([("ti4f", "Ti", 47.88, 1.1e6, 500.0)])}
    entry, tables = _make_existing("base", "v1.0",
                                    atom_rows=[("ti4f", "Ti", 47.88, 1.0e6, 500.0)], bond_rows=None)
    coll = detect_collisions(new_tables, [entry], lambda _p: tables)
    assert len(coll) == 1
    assert coll[0].status == "conflict"
    assert "lj_a" in coll[0].disagrees_on
    assert count_conflicts(coll) == (1, 0)


def test_bond_collisions_detected():
    new_tables = {
        "atom_types": _at_df([("ti4f", "Ti", 47.88, 1e6, 500.0)]),
        "bonds": _bonds_df([("ti4f", "o", 280.0, 1.8)]),
    }
    entry, tables = _make_existing(
        "base", "v1.0",
        atom_rows=[("ti4f", "Ti", 47.88, 1e6, 500.0)],
        bond_rows=[("ti4f", "o", 300.0, 1.8)],
    )
    coll = detect_collisions(new_tables, [entry], lambda _p: tables)
    bond_conflicts = [c for c in coll if c.scope == "bonds"]
    assert len(bond_conflicts) == 1
    assert bond_conflicts[0].status == "conflict"
    assert "k" in bond_conflicts[0].disagrees_on


def test_counts_conflicts_vs_duplicates_separately():
    new_tables = {"atom_types": _at_df([
        ("shared_same", "X", 1.0, 1.0, 1.0),
        ("shared_diff", "X", 1.0, 2.0, 1.0),
    ])}
    entry, tables = _make_existing("base", "v1.0",
                                    atom_rows=[("shared_same", "X", 1.0, 1.0, 1.0),
                                               ("shared_diff", "X", 1.0, 1.0, 1.0)],
                                    bond_rows=None)
    coll = detect_collisions(new_tables, [entry], lambda _p: tables)
    n_conf, n_dup = count_conflicts(coll)
    assert n_conf == 1 and n_dup == 1
