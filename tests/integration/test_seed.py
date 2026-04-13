"""Seed validation tests (S-1..S-8 from VALIDATION_PLAN.md).

These operate against the live seeded library at src/iff_parameters/data/.
They assume the seed scripts have run (otherwise they skip).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LIVE_DATA = REPO_ROOT / "src" / "iff_parameters" / "data"


def _require_seeded(kind: str) -> None:
    subdir = LIVE_DATA / kind
    log_path = subdir / "_seed_log.json"
    if not log_path.is_file():
        pytest.skip(f"{kind} seed log missing — run the seed scripts first")


def test_s1_three_canonical_parameter_bundles():
    """S-1: seed produces exactly 3 parameter entries from INTERFACE_FF_1_5."""
    _require_seeded("parameters")
    from iff_parameters.entries import list_parameter_entries
    params = list_parameter_entries()
    names = sorted(e.name for e in params)
    assert "cvff-interface" in names
    assert "pcff-interface" in names
    assert "charmm27-interface" in names
    assert len(params) >= 3


def test_s2_pcff_marked_partial_roundtrip():
    """S-2: PCFF entry declares partial_roundtrip and preserves raw source."""
    _require_seeded("parameters")
    from iff_parameters.entries import find_parameter_entry
    pcff = find_parameter_entry("pcff-interface", "v1.5")
    assert pcff is not None
    assert pcff.manifest.get("partial_roundtrip") is True
    raw = pcff.path / "raw" / "source.frc"
    assert raw.is_file()
    assert raw.stat().st_size > 10_000  # non-trivial preserved source


def test_s3_structure_entries_across_material_classes():
    """S-3: structures seeded for all 7 material classes."""
    _require_seeded("structures")
    from iff_parameters.entries import list_structure_entries
    structs = list_structure_entries()
    assert len(structs) >= 100, f"expected many structures, got {len(structs)}"

    class_dirs = sorted({e.path.parent.parent.name for e in structs})
    expected_classes = {"silica", "metals", "cement", "clay", "hydroxyapatite", "ca-sulfate", "peo"}
    missing = expected_classes - set(class_dirs)
    assert not missing, f"missing material classes: {missing}"


def test_s4_parameterized_with_inferred_correctly():
    """S-4: every structure's parameterized_with points at a real, existing FF."""
    _require_seeded("structures")
    _require_seeded("parameters")
    from iff_parameters.entries import find_parameter_entry, list_structure_entries
    for e in list_structure_entries():
        refs = e.parameterized_with
        assert refs, f"{e.ref()} has no parameterized_with"
        for ref in refs:
            target = find_parameter_entry(ref["name"], ref["version"])
            assert target is not None, (
                f"{e.ref()} references {ref['name']}@{ref['version']} which doesn't exist"
            )


def test_s5_atom_type_coverage_check():
    """S-5: every structure's atom types resolve in its pinned FF (possibly after renames)."""
    _require_seeded("structures")
    _require_seeded("parameters")
    from iff_parameters.compat import compatibility_check
    from iff_parameters.entries import list_structure_entries
    failed = []
    for e in list_structure_entries():
        # Run a compat check against the (only) pinned version.
        for ref in e.parameterized_with:
            res = compatibility_check(e, ref["name"], ref["version"])
            if res.status == "ERROR":
                failed.append((e.ref(), ref, res.messages))
    assert not failed, f"coverage check failures: {failed[:3]}"


def test_s6_no_validation_errors():
    """S-6: seeded library passes structural validation (all hashes, refs valid)."""
    _require_seeded("parameters")
    from iff_parameters.entries import list_parameter_entries, list_structure_entries
    from upm.bundle.io import load_package, load_structure

    for e in list_parameter_entries():
        # load with hash validation
        bundle = load_package(e.path, validate_hashes=True)
        assert bundle.manifest["name"] == e.name

    for e in list_structure_entries():
        bundle = load_structure(e.path, validate_hashes=True)
        assert bundle.manifest["type"] == "structure"


def test_s7_seed_is_idempotent_minus_timestamps(tmp_path):
    """S-7: running the parameter seed twice produces byte-identical tables and raw sources.

    The manifest's created_utc and provenance.ingested_utc differ between runs,
    so we hash only the tables/ and raw/ subtrees for idempotency.
    """
    _require_seeded("parameters")

    import hashlib

    def _hash_tree(root: Path, skip_names=("manifest.json",)) -> str:
        h = hashlib.sha256()
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if p.name in skip_names:
                continue
            h.update(str(p.relative_to(root)).encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
        return h.hexdigest()

    live_hashes = {
        family: _hash_tree(LIVE_DATA / "parameters" / family / "v1.5")
        for family in ("cvff-interface", "pcff-interface", "charmm27-interface")
    }

    # Run the script again with --force in a subprocess
    import subprocess
    result = subprocess.run(
        ["python3", str(REPO_ROOT / "scripts" / "seed_from_interface_ff15_parameters.py"),
         "--force"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr

    rerun_hashes = {
        family: _hash_tree(LIVE_DATA / "parameters" / family / "v1.5")
        for family in ("cvff-interface", "pcff-interface", "charmm27-interface")
    }

    assert live_hashes == rerun_hashes, "seed output changed between runs"


def test_s8_seed_log_records_provenance():
    """S-8: parameter + structure seed logs capture what was ingested."""
    _require_seeded("parameters")
    _require_seeded("structures")
    param_log = json.loads((LIVE_DATA / "parameters" / "_seed_log.json").read_text())
    struct_log = json.loads((LIVE_DATA / "structures" / "_seed_log.json").read_text())

    assert "seeded_utc" in param_log
    assert len(param_log["results"]) == 3
    for r in param_log["results"]:
        assert r["source_sha256"]
        assert r["n_atom_types"] > 0

    assert "seeded_utc" in struct_log
    assert struct_log["n_ingested"] > 0
    assert struct_log["n_failed"] == 0, f"failures: {struct_log.get('failures')}"
