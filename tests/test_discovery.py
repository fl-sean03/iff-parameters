"""Test UPM entry-point discovery integration."""
from __future__ import annotations

import json
from pathlib import Path

from iff_parameters import get_data_dir, list_available


def test_get_data_dir_returns_path() -> None:
    result = get_data_dir()
    assert isinstance(result, Path)
    assert result.name == "data"


def test_list_available_returns_list() -> None:
    result = list_available()
    assert isinstance(result, list)


def test_local_discovery(tmp_path: Path) -> None:
    from upm.registry.discovery import discover_local_packages

    pkg_dir = tmp_path / "test-ff" / "v1"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "manifest.json").write_text(
        json.dumps({"name": "test-ff", "version": "v1", "schema_version": "upm-1.0"})
    )
    result = discover_local_packages(tmp_path)
    assert len(result) == 1
    assert result[0].name == "test-ff"
