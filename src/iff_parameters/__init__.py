"""INTERFACE Force Field parameter + structure library.

Central, versioned library of force field parameters and
pre-parameterized molecular structures. Discoverable by UPM's registry
via the 'upm.data_packages' entry point group.

See docs/ARCHITECTURE.md for the data model.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__version__ = "0.2.0a0"

_ARCHIVE_DIRNAME = "archive"


def get_data_dir() -> Path:
    """Return path to the data directory.

    Registered in pyproject.toml under [project.entry-points."upm.data_packages"].
    """
    return Path(__file__).parent / "data"


def _iter_entry_manifests(entry_type: str | None = None):
    """Yield (manifest_path, manifest_dict) for every live entry.

    Skips anything under ``data/archive/``. If ``entry_type`` is given
    ('parameters' or 'structure'), also filters by manifest ``type``.
    """
    data_dir = get_data_dir()
    if not data_dir.is_dir():
        return
    for manifest_path in sorted(data_dir.rglob("manifest.json")):
        if _ARCHIVE_DIRNAME in manifest_path.parts:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if entry_type is not None and manifest.get("type") != entry_type:
            continue
        yield manifest_path, manifest


def list_available(entry_type: str | None = None) -> list[dict[str, Any]]:
    """List live entries with basic metadata.

    Args:
        entry_type: 'parameters', 'structure', or None for both.

    Returns:
        List of dicts with keys: name, version, type, materials, format,
        author, doi, path. Deprecated entries are included; filter in UI.
    """
    results: list[dict[str, Any]] = []
    for manifest_path, manifest in _iter_entry_manifests(entry_type):
        provenance = manifest.get("provenance", {})
        results.append({
            "name": manifest.get("name", "unknown"),
            "version": manifest.get("version", "unknown"),
            "type": manifest.get("type", "parameters"),
            "materials": provenance.get("materials", []),
            "format": _detect_format(provenance.get("source_file", "")),
            "source_file": provenance.get("source_file", ""),
            "author": provenance.get("author", ""),
            "doi": provenance.get("publication_doi"),
            "deprecated": manifest.get("deprecated", False),
            "supersedes": manifest.get("supersedes"),
            "path": str(manifest_path.parent),
        })
    return results


def search_by_material(material: str) -> list[dict[str, Any]]:
    """Find entries (parameters or structures) covering a material."""
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
    elif source_file.endswith((".car", ".mdf", ".pdb", ".psf", ".cif")):
        return "structure"
    return "unknown"


__all__ = [
    "__version__",
    "get_data_dir",
    "list_available",
    "search_by_material",
]
