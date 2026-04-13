"""Tolerant CAR (Materials Studio archive) atom parser.

Handles format quirks in INTERFACE_FF_1_5 distribution that USM's parser
rejects — `ca++` atom types, unusual mol_label widths, non-numeric
mol_index values. Extracts the minimum needed for structure entry
ingestion: id, element, ff_type, charge, x, y, z.

If USM is installed and can parse the file, that path is preferred.
Only the tolerant fallback lives here so it's usable without USM.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

_SKIP_PREFIXES = ("!", "#", "PBC", "Materials Studio", "!DATE")


def parse_car_atoms_tolerant(text: str) -> pd.DataFrame:
    """Extract atoms from raw CAR text. Ignores non-atom lines.

    Returns a DataFrame with columns: id, element, ff_type, charge, x, y, z.
    """
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in ("end", "END"):
            continue
        if stripped[0] in "!#" or line.startswith(_SKIP_PREFIXES):
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        try:
            x = float(parts[1])
            y = float(parts[2])
            z = float(parts[3])
            charge = float(parts[-1])
        except ValueError:
            continue
        rows.append({
            "id": len(rows) + 1,
            "element": parts[7],
            "ff_type": parts[6],
            "charge": charge,
            "x": x, "y": y, "z": z,
        })
    return pd.DataFrame(rows)


def load_car_atoms(path: str | Path) -> pd.DataFrame:
    """USM-preferred, tolerant fallback. Always returns canonical columns."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    # Try USM first
    try:
        from usm.io.car import load_car
        usm = load_car(str(path))
        if len(usm.atoms) > 0 and "atom_type" in usm.atoms.columns:
            return pd.DataFrame({
                "id": usm.atoms["aid"].astype(int) + 1,
                "element": usm.atoms["element"].astype(str),
                "ff_type": usm.atoms["atom_type"].astype(str),
                "charge": usm.atoms["charge"].astype(float),
                "x": usm.atoms["x"].astype(float),
                "y": usm.atoms["y"].astype(float),
                "z": usm.atoms["z"].astype(float),
            })
    except Exception:
        pass
    atoms = parse_car_atoms_tolerant(text)
    if len(atoms) == 0:
        raise ValueError(f"no atoms parsed from {path} (tried USM + tolerant)")
    return atoms


__all__ = ["parse_car_atoms_tolerant", "load_car_atoms"]
