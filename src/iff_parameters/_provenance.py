"""Provenance metadata schema and utilities for IFF parameter bundles."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Provenance:
    """Extended provenance metadata for a force field bundle."""

    author: str
    lab: str = "Heinz Lab, CU Boulder"
    date_created: str = ""
    publication_doi: str | None = None
    source_file: str = ""
    source_sha256: str = ""
    parent_ff: str | None = None
    materials: list[str] = field(default_factory=list)
    notes: str = ""
    ingested_utc: str = ""

    def __post_init__(self) -> None:
        if not self.ingested_utc:
            self.ingested_utc = (
                datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_of_file(path: Path) -> str:
    """Compute hex-encoded SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# Default provenance for the 7 canonical files.
CANONICAL_PROVENANCE: dict[str, dict[str, Any]] = {
    "cvff_IFF_metal_oxides_v2.frc": {
        "author": "Hendrik Heinz",
        "lab": "Heinz Lab, CU Boulder",
        "date_created": "2013-01-01",
        "publication_doi": "10.1021/la3038846",
        "parent_ff": "cvff_interface_v1_5",
        "materials": ["Al2O3", "SiO2", "clays", "alumina"],
        "notes": "IFF metal oxides v2 — Al2O3, SiO2, clays",
    },
    "cvff_iff_ILs.frc": {
        "author": "Hendrik Heinz",
        "lab": "Heinz Lab, CU Boulder",
        "date_created": "2018-01-01",
        "parent_ff": "cvff_interface_v1_5",
        "materials": ["ionic_liquids", "CO2", "MOFs"],
        "notes": "Ionic liquids, CO2, and MOF parameters",
    },
    "cvff_interface_v1_5.frc": {
        "author": "Hendrik Heinz",
        "lab": "Heinz Lab, CU Boulder",
        "date_created": "2015-11-25",
        "publication_doi": "10.1021/la3038846",
        "parent_ff": None,
        "materials": ["Ag", "Al", "Au", "Cu", "Ni", "Pb", "Pd", "Pt", "silica", "clays"],
        "notes": "Canonical IFF v1.5 CVFF from hendrikheinz GitHub",
    },
    "IFF_CHARMM36_metal_and_alumina_phases_V8.prm": {
        "author": "Hendrik Heinz",
        "lab": "Heinz Lab, CU Boulder",
        "date_created": "2021-01-01",
        "parent_ff": "charmm36",
        "materials": ["Ag", "Al", "Au", "Cu", "Ni", "Pb", "Pd", "Pt", "Al2O3", "alumina"],
        "notes": "IFF CHARMM36 v8 — metals + alumina phases",
    },
}
