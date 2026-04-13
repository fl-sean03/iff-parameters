"""Entry discovery and resolution for the IFF parameter library.

An entry is a versioned directory under `data/parameters/<family>/<version>/`
or `data/structures/<class>/<model>/<version>/`, each with a `manifest.json`.

This module provides typed wrappers around manifest data, version listings
per family, and simple lookups — no heavy table loading (see `pull.py` and
upm.registry.index for that).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import total_ordering
from pathlib import Path
from typing import Any, Iterator

from . import get_data_dir

_ARCHIVE_DIRNAME = "archive"

_VERSION_RE = re.compile(r"^v(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)$")


@total_ordering
@dataclass(frozen=True, order=False)
class Version:
    """Parsed version identifier.

    Accepts ``v1``, ``v1.0``, ``v1.0.1``, ``v1.0-mxene``. Comparisons sort
    by (major, minor, patch); non-numeric suffixes break ties lexicographically.
    """
    raw: str
    major: int
    minor: int
    patch: int
    suffix: str

    @classmethod
    def parse(cls, s: str) -> "Version":
        m = _VERSION_RE.match(s.strip())
        if not m:
            raise ValueError(f"unparseable version string: {s!r}")
        major = int(m.group(1))
        minor = int(m.group(2) or 0)
        patch = int(m.group(3) or 0)
        suffix = m.group(4) or ""
        return cls(raw=s.strip(), major=major, minor=minor, patch=patch, suffix=suffix)

    def tuple(self) -> tuple[int, int, int, str]:
        return (self.major, self.minor, self.patch, self.suffix)

    def __lt__(self, other: "Version") -> bool:   # type: ignore[override]
        if not isinstance(other, Version):
            return NotImplemented
        return self.tuple() < other.tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.tuple() == other.tuple()

    def __hash__(self) -> int:
        return hash(self.tuple())

    def __str__(self) -> str:
        return self.raw


@dataclass(frozen=True)
class Entry:
    """Typed view over a manifest.json on disk."""
    path: Path
    manifest: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.manifest.get("name", ""))

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", ""))

    @property
    def type(self) -> str:
        return str(self.manifest.get("type", "parameters"))

    @property
    def deprecated(self) -> bool:
        return bool(self.manifest.get("deprecated", False))

    @property
    def supersedes(self) -> str | None:
        v = self.manifest.get("supersedes")
        return str(v) if v is not None else None

    @property
    def breaking(self) -> bool:
        return bool(self.manifest.get("breaking", False))

    @property
    def renames(self) -> dict[str, str]:
        r = self.manifest.get("renames") or {}
        return {str(k): str(v) for k, v in r.items()} if isinstance(r, dict) else {}

    @property
    def atom_type_family(self) -> str | None:
        v = self.manifest.get("atom_type_family")
        return str(v) if v is not None else None

    @property
    def parameterized_with(self) -> list[dict[str, str]]:
        pw = self.manifest.get("parameterized_with") or []
        return [{"name": str(x["name"]), "version": str(x["version"])}
                for x in pw if isinstance(x, dict) and "name" in x and "version" in x]

    @property
    def lock_to_original(self) -> bool:
        return bool(self.manifest.get("lock_to_original", False))

    def parsed_version(self) -> Version:
        return Version.parse(self.version)

    def ref(self) -> str:
        return f"{self.name}@{self.version}"


def _iter_manifest_paths(data_dir: Path, subdir: str | None = None) -> Iterator[Path]:
    root = data_dir if subdir is None else data_dir / subdir
    if not root.is_dir():
        return
    for mp in sorted(root.rglob("manifest.json")):
        if _ARCHIVE_DIRNAME in mp.parts:
            continue
        yield mp


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def iter_entries(entry_type: str | None = None) -> Iterator[Entry]:
    """Yield every non-archived manifest as a typed Entry.

    Args:
        entry_type: 'parameters', 'structure', or None for both.
    """
    data_dir = get_data_dir()
    subdir = None
    if entry_type == "parameters":
        subdir = "parameters"
    elif entry_type == "structure":
        subdir = "structures"
    for mp in _iter_manifest_paths(data_dir, subdir):
        manifest = _read_manifest(mp)
        if manifest is None:
            continue
        if entry_type is not None and manifest.get("type") != entry_type:
            continue
        yield Entry(path=mp.parent, manifest=manifest)


def list_parameter_entries() -> list[Entry]:
    return list(iter_entries("parameters"))


def list_structure_entries() -> list[Entry]:
    return list(iter_entries("structure"))


@dataclass
class FamilyVersions:
    """All versions of a single parameter family."""
    family: str
    entries: list[Entry] = field(default_factory=list)

    def sorted_descending(self) -> list[Entry]:
        return sorted(self.entries, key=lambda e: e.parsed_version(), reverse=True)

    def latest(self, include_deprecated: bool = False) -> Entry | None:
        candidates = self.sorted_descending()
        if not include_deprecated:
            candidates = [e for e in candidates if not e.deprecated]
        return candidates[0] if candidates else None

    def get(self, version: str) -> Entry | None:
        for e in self.entries:
            if e.version == version:
                return e
        return None


def index_family_versions(entries: list[Entry] | None = None) -> dict[str, FamilyVersions]:
    """Group parameter entries by family name."""
    if entries is None:
        entries = list_parameter_entries()
    out: dict[str, FamilyVersions] = {}
    for e in entries:
        out.setdefault(e.name, FamilyVersions(family=e.name)).entries.append(e)
    return out


def find_parameter_entry(name: str, version: str) -> Entry | None:
    """Locate a specific parameter entry by family + version."""
    for e in iter_entries("parameters"):
        if e.name == name and e.version == version:
            return e
    return None


def resolve_parameter_ref(ref: str) -> Entry | None:
    """Accept 'name@version' or 'name/version' and return the Entry or None."""
    if "@" in ref:
        name, version = ref.split("@", 1)
    elif "/" in ref:
        name, version = ref.rsplit("/", 1)
    else:
        return None
    return find_parameter_entry(name.strip(), version.strip())


__all__ = [
    "Version",
    "Entry",
    "FamilyVersions",
    "iter_entries",
    "list_parameter_entries",
    "list_structure_entries",
    "index_family_versions",
    "find_parameter_entry",
    "resolve_parameter_ref",
]
