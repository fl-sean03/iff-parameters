"""Validator (scripts/validate.py) tests — ensure it catches all V-* cases."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATE = REPO_ROOT / "scripts" / "validate.py"


def _run(data_dir: Path, extra_args: list[str] | None = None) -> tuple[int, str, str]:
    cmd = [sys.executable, str(VALIDATE), "--data-dir", str(data_dir)]
    if extra_args:
        cmd.extend(extra_args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _seed_clean_library(library) -> None:
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)])
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v1.0"}],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
    )


def test_clean_library_passes(library):
    _seed_clean_library(library)
    code, out, _ = _run(library.root)
    assert code == 0, f"expected exit 0, got {code}\n{out}"
    assert "errors:   0" in out


def test_v2_forward_ref_errors(library):
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="missing",
        parameterized_with=[{"name": "missing", "version": "v1.0"}],
    )
    code, out, _ = _run(library.root)
    assert code == 1
    assert "V-2" in out


def test_v5_hash_mismatch_errors(library):
    _seed_clean_library(library)
    # Tamper with a CSV
    at = library.parameters_dir / "fam" / "v1.0" / "tables" / "atom_types.csv"
    at.write_text(at.read_text() + "\n# tampered\n")
    code, out, _ = _run(library.root)
    assert code == 1
    assert "V-5" in out
    assert "sha256 mismatch" in out


def test_v7_circular_supersedes_errors(library):
    library.add_param("fam", "v1.0", atom_types=[("a", "A", 1, 1, 1)],
                      supersedes="v1.1")
    library.add_param("fam", "v1.1", atom_types=[("a", "A", 2, 2, 1)],
                      supersedes="v1.0")
    library.add_structure(
        "m", "v1.0", material_class="test",
        atom_type_family="fam",
        parameterized_with=[{"name": "fam", "version": "v1.0"}],
        atoms=[(1, "A", "a", 0, 0, 0, 0)],
    )
    code, out, _ = _run(library.root)
    assert code == 1
    assert "V-7" in out


def test_v9_cross_family_conflict_warns_not_errors(library):
    """Two families disagreeing on an atom type with identical name is a WARNING, not an error."""
    library.add_param("a", "v1.0",
                      atom_types=[("shared", "X", 1.0, 1.0, 1.0)])
    library.add_param("b", "v1.0",
                      atom_types=[("shared", "X", 2.0, 2.0, 1.0)])
    code, out, _ = _run(library.root)
    # errors: 0, at least one V-9 warning
    assert code == 0
    assert "V-9" in out


def test_json_report_written(library, tmp_path):
    _seed_clean_library(library)
    report_path = tmp_path / "report.json"
    code, _, _ = _run(library.root, ["--json", str(report_path)])
    assert code == 0
    assert report_path.is_file()
    data = json.loads(report_path.read_text())
    assert "errors" in data and "warnings" in data and "info" in data
    assert data["info"]["n_entries"] == 2
    assert data["info"]["by_type"] == {"parameters": 1, "structure": 1}


def test_strict_mode_fails_on_warnings(library):
    library.add_param("a", "v1.0",
                      atom_types=[("shared", "X", 1.0, 1.0, 1.0)])
    library.add_param("b", "v1.0",
                      atom_types=[("shared", "X", 2.0, 2.0, 1.0)])
    code, _, _ = _run(library.root, ["--strict"])
    assert code == 1
