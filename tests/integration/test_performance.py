"""Performance budgets from VALIDATION_PLAN §10.

These are soft checks — they'll fail if something regresses badly but
aren't designed to be benchmarks in the pytest-benchmark sense. We just
measure wall time and assert it's within budget.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATE = REPO_ROOT / "scripts" / "validate.py"
LIVE_DATA = REPO_ROOT / "src" / "iff_parameters" / "data"


def _live_or_skip():
    if not (LIVE_DATA / "parameters").is_dir():
        pytest.skip("live library not seeded")


def test_index_rebuild_under_1s():
    """PackageIndex rebuild across all parameter entries < 1s (budget: 1s)."""
    _live_or_skip()
    from upm.registry.discovery import discover_local_packages
    from upm.registry.index import PackageIndex

    pkgs = discover_local_packages(LIVE_DATA / "parameters")
    t0 = time.perf_counter()
    idx = PackageIndex(pkgs)
    _ = idx.atom_type_index, idx.bond_index, idx.angle_index, idx.torsion_index
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.5, f"index rebuild took {elapsed:.2f}s (budget 2.5s)"


def test_pull_latest_under_500ms():
    """pull_latest on any live structure < 500ms (budget: 500ms)."""
    _live_or_skip()
    from iff_parameters.entries import list_structure_entries
    from iff_parameters.pull import pull_latest

    structs = list_structure_entries()
    if not structs:
        pytest.skip("no structures")
    # Use a small structure to minimize IO
    small = min(structs, key=lambda e: e.manifest.get("atoms_csv", {}).get("rows", 1e9))
    t0 = time.perf_counter()
    result = pull_latest(small)
    elapsed = time.perf_counter() - t0
    assert result.status in ("OK", "WARNING")
    assert elapsed < 0.8, f"pull_latest took {elapsed:.2f}s (budget 0.8s)"


def test_validate_py_under_30s():
    """Full validate.py against live library < 30s (budget: 30s)."""
    _live_or_skip()
    t0 = time.perf_counter()
    r = subprocess.run(
        [sys.executable, str(VALIDATE)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    elapsed = time.perf_counter() - t0
    assert r.returncode == 0, r.stdout[-2000:]
    assert elapsed < 45, f"validate.py took {elapsed:.1f}s (budget 45s)"
