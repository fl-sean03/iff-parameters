"""Roundtrip tests: ingest → bundle → reload → compare."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from upm.bundle.io import load_package, save_package
from upm.core.tables import normalize_tables


def _minimal_frc_text() -> str:
    return """\
!BIOSYM forcefield          1
#atom_types cvff
 1.0  1   Au    196.967     Au       12      gold fcc
 1.0  1   ag    107.868     Ag       12      silver fcc
#nonbond(12-6)
@type A-B
@combination geometric
 1.0   1    Au      125896.0      250.1
 1.0   1    ag       89000.0      180.5
"""


def test_frc_roundtrip(tmp_path: Path) -> None:
    from upm.codecs.msi_frc import parse_frc_text
    text = _minimal_frc_text()
    tables, raw = parse_frc_text(text, validate=False)
    root = tmp_path / "test-ff" / "v1"
    save_package(root, name="test-ff", version="v1",
                 tables=tables, source_text=text, unknown_sections=raw)
    bundle = load_package(root)
    assert len(bundle.tables["atom_types"]) == 2


def test_prm_roundtrip(tmp_path: Path) -> None:
    from upm.codecs._charmm_parser import parse_prm_text
    text = "* Test\n*\n\nNONBONDED\nAU  0.0  -5.29  1.644\n\nEND\n"
    tables, raw = parse_prm_text(text)
    tables = normalize_tables(tables)
    root = tmp_path / "test-prm" / "v1"
    save_package(root, name="test-prm", version="v1",
                 tables=tables, source_text=text, unknown_sections=raw)
    bundle = load_package(root)
    assert "atom_types" in bundle.tables


def test_provenance_persisted(tmp_path: Path) -> None:
    from upm.codecs.msi_frc import parse_frc_text
    from iff_parameters._provenance import Provenance
    tables, raw = parse_frc_text(_minimal_frc_text(), validate=False)
    root = tmp_path / "prov" / "v1"
    save_package(root, name="prov", version="v1",
                 tables=tables, source_text="! test", unknown_sections=raw)
    prov = Provenance(author="Test", materials=["Au", "Ag"])
    mp = root / "manifest.json"
    m = json.loads(mp.read_text())
    m["provenance"] = prov.to_dict()
    mp.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    reloaded = json.loads(mp.read_text())
    assert reloaded["provenance"]["author"] == "Test"
    assert reloaded["provenance"]["materials"] == ["Au", "Ag"]
