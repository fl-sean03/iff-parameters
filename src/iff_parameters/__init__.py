"""INTERFACE Force Field parameters for UPM.

Provides curated Heinz Lab force field parameter bundles discoverable
by UPM's registry via the 'upm.data_packages' entry point group.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__version__ = "0.1.0"


def get_data_dir() -> Path:
    """Return path to the data directory containing UPM bundles.

    This is the entry point callable registered in pyproject.toml under
    [project.entry-points."upm.data_packages"]. UPM's discover_packages()
    calls this to locate installed parameter bundles.
    """
    return Path(__file__).parent / "data"


def list_available() -> list[dict[str, Any]]:
    """List all available parameter sets with metadata.

    Returns:
        List of dicts with keys: name, version, materials, format, source_file, path.
    """
    data_dir = get_data_dir()
    results: list[dict[str, Any]] = []
    if not data_dir.is_dir():
        return results

    for manifest_path in sorted(data_dir.rglob("manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            provenance = manifest.get("provenance", {})
            results.append({
                "name": manifest.get("name", "unknown"),
                "version": manifest.get("version", "unknown"),
                "materials": provenance.get("materials", []),
                "format": _detect_format(provenance.get("source_file", "")),
                "source_file": provenance.get("source_file", ""),
                "author": provenance.get("author", ""),
                "doi": provenance.get("publication_doi"),
                "path": str(manifest_path.parent),
            })
        except Exception:
            continue
    return results


def search_by_material(material: str) -> list[dict[str, Any]]:
    """Find bundles that cover a given material (case-insensitive)."""
    material_lower = material.lower()
    return [
        entry for entry in list_available()
        if any(material_lower in m.lower() for m in entry.get("materials", []))
    ]


def _detect_format(source_file: str) -> str:
    if source_file.endswith(".frc"):
        return "cvff"
    elif source_file.endswith(".prm"):
        return "charmm"
    return "unknown"


__all__ = [
    "__version__",
    "get_data_dir",
    "list_available",
    "search_by_material",
]
