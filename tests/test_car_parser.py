"""Unit tests for iff_parameters.car_parser (tolerant CAR parsing)."""

from __future__ import annotations

from iff_parameters.car_parser import parse_car_atoms_tolerant


_SIMPLE_CAR = """!BIOSYM archive 3
PBC=ON
Materials Studio Generated CAR File
!DATE Fri Jan 1 00:00:00 2020
PBC    4.9   4.9   5.4    90.0   90.0  120.0 (P1)
O1       1.0   2.0   3.0   XXXX  1      oc23    O  -0.550
Si1      0.0   0.0   0.0   XXXX  1      sc4     Si  1.100
end
end
"""

# Real-world tricky cases from INTERFACE_FF_1_5: `ca++` atom type, 3-char
# mol_label, alphanumeric mol_index.
_TRICKY_CAR = """!BIOSYM archive 3
PBC=ON
!DATE Thu May 31 03:37:27 2012
PBC    4.9   4.9   5.4    90.0   90.0  120.0 (P1)
CA1     -1.0   1.0   2.0   XXX   ND     ca++    Ca  1.500
SI1      1.6   8.4   7.7   XXX   A1     sy1     Si  1.100
end
end
"""


def test_parses_simple_car():
    df = parse_car_atoms_tolerant(_SIMPLE_CAR)
    assert len(df) == 2
    assert list(df.columns) == ["id", "element", "ff_type", "charge", "x", "y", "z"]
    assert df.iloc[0]["ff_type"] == "oc23"
    assert df.iloc[1]["ff_type"] == "sc4"
    assert abs(df.iloc[0]["charge"] - (-0.550)) < 1e-9


def test_handles_tricky_atom_types_and_mol_labels():
    """ca++ atom type and 3-char mol_label (things USM rejects)."""
    df = parse_car_atoms_tolerant(_TRICKY_CAR)
    assert len(df) == 2
    assert df.iloc[0]["ff_type"] == "ca++"
    assert df.iloc[0]["element"] == "Ca"
    assert abs(df.iloc[0]["charge"] - 1.500) < 1e-9
    assert df.iloc[1]["ff_type"] == "sy1"


def test_skips_non_atom_lines():
    text = "!header\n\nPBC   1  1  1   90 90 90 (P1)\nend\nend\n"
    df = parse_car_atoms_tolerant(text)
    assert len(df) == 0


def test_skips_lines_with_insufficient_fields():
    text = "!BIOSYM archive 3\nO1   1.0  2.0\nend\n"
    df = parse_car_atoms_tolerant(text)
    assert len(df) == 0


def test_ids_are_1_indexed():
    df = parse_car_atoms_tolerant(_SIMPLE_CAR)
    assert list(df["id"]) == [1, 2]
