"""Shared fixtures for iff-parameters tests.

Provides a ``library(tmp_path, monkeypatch)`` fixture that sets
``iff_parameters.get_data_dir`` to a tmp tree and gives you helpers
for writing parameter and structure entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from upm.bundle.io import save_package, save_structure


def _atom_types_df(types: list[tuple[str, str, float, float, float]]) -> pd.DataFrame:
    """(name, element, lj_a, lj_b, mass) -> DataFrame with canonical columns."""
    return pd.DataFrame({
        "atom_type": [t[0] for t in types],
        "element": [t[1] for t in types],
        "mass_amu": [t[4] for t in types],
        "vdw_style": ["lj_A_B"] * len(types),
        "lj_a": [t[2] for t in types],
        "lj_b": [t[3] for t in types],
        "notes": [""] * len(types),
    })


def _bonds_df(rows: list[tuple[str, str, float, float]]) -> pd.DataFrame:
    """(t1, t2, k, r0)."""
    return pd.DataFrame({
        "t1": [r[0] for r in rows],
        "t2": [r[1] for r in rows],
        "style": ["harm"] * len(rows),
        "k": [r[2] for r in rows],
        "r0": [r[3] for r in rows],
        "source": [""] * len(rows),
    })


@dataclass
class LibraryFixture:
    root: Path

    @property
    def parameters_dir(self) -> Path:
        return self.root / "parameters"

    @property
    def structures_dir(self) -> Path:
        return self.root / "structures"

    def add_param(
        self,
        name: str,
        version: str,
        *,
        atom_types: list[tuple[str, str, float, float, float]] | None = None,
        bonds: list[tuple[str, str, float, float]] | None = None,
        supersedes: str | None = None,
        parent_ff: str | None = None,
        renames: dict[str, str] | None = None,
        breaking: bool = False,
        deprecated: bool = False,
        deprecation_reason: str | None = None,
        overrides: list[dict[str, Any]] | None = None,
        partial_roundtrip: bool = False,
        provenance: dict[str, Any] | None = None,
    ) -> Path:
        root = self.parameters_dir / name / version
        tables: dict[str, Any] = {}
        if atom_types is not None:
            tables["atom_types"] = _atom_types_df(atom_types)
        if bonds is not None:
            tables["bonds"] = _bonds_df(bonds)
        save_package(
            root,
            name=name, version=version,
            tables=tables,
            source_text=f"# {name}@{version}\n",
            supersedes=supersedes,
            parent_ff=parent_ff,
            renames=renames,
            breaking=breaking,
            deprecated=deprecated,
            deprecation_reason=deprecation_reason,
            overrides=overrides,
            partial_roundtrip=partial_roundtrip,
            provenance=provenance or {
                "author": "Test",
                "source_file": "test.frc",
                "source_sha256": "deadbeef",
            },
        )
        return root

    def add_structure(
        self,
        model_name: str,
        version: str,
        *,
        material_class: str = "test",
        atoms: list[tuple[int, str, str, float, float, float, float]] | None = None,
        atom_type_family: str,
        parameterized_with: list[dict[str, str]],
        lock_to_original: bool = False,
        validated_with: list[dict[str, str]] | None = None,
        supersedes: str | None = None,
    ) -> Path:
        if atoms is None:
            atoms = [(1, "Ti", "ti4f", 1.5, 0.0, 0.0, 0.0)]
        atoms_df = pd.DataFrame({
            "id": [a[0] for a in atoms],
            "element": [a[1] for a in atoms],
            "ff_type": [a[2] for a in atoms],
            "charge": [a[3] for a in atoms],
            "x": [a[4] for a in atoms],
            "y": [a[5] for a in atoms],
            "z": [a[6] for a in atoms],
        })
        root = self.structures_dir / material_class / model_name / version
        save_structure(
            root,
            name=model_name, version=version,
            atoms_df=atoms_df,
            geometry_text="# geometry stub\n",
            geometry_format="car",
            atom_type_family=atom_type_family,
            parameterized_with=parameterized_with,
            lock_to_original=lock_to_original,
            validated_with=validated_with,
            supersedes=supersedes,
            provenance={"author": "Test", "materials": [material_class]},
        )
        return root


@pytest.fixture
def library(tmp_path, monkeypatch) -> LibraryFixture:
    """Give the test a fresh library rooted at tmp_path/data.

    Patches ``iff_parameters.get_data_dir`` so all module-level helpers
    (iter_entries, index_family_versions, etc.) see the test library.
    """
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "parameters").mkdir()
    (data_root / "structures").mkdir()

    import iff_parameters
    monkeypatch.setattr(iff_parameters, "get_data_dir", lambda: data_root)

    # Force reload of dependent modules' import-time caches.
    import importlib
    import iff_parameters.entries
    importlib.reload(iff_parameters.entries)

    return LibraryFixture(root=data_root)
