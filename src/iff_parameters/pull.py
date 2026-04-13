"""Structure pull operations.

Three well-defined operations over the immutable library:

- ``pull_latest(structure)`` — newest non-deprecated compatible version of
  each FF family the structure is parameterized with. Auto-applies renames.
  Fallback: walks backward to find the newest compatible version. Honors
  ``lock_to_original``.
- ``pull_original(structure)`` — exact pin from manifest.
- ``pull_version(structure, family, version)`` — explicit; no silent fallback.

Return value (PullResult): structure bundle + dict of family -> resolved
parameter bundle, plus a metadata block describing any renames applied,
fallbacks taken, breaking changes crossed, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .compat import CompatibilityResult, compatibility_check
from .entries import Entry, find_parameter_entry, index_family_versions


@dataclass
class PullResult:
    """Outcome of a pull operation.

    Attributes:
        structure: the StructureBundle from upm.bundle.io.load_structure.
        parameters: family_name -> PackageBundle (upm.bundle.io.load_package).
        resolutions: family_name -> per-family resolution metadata.
        status: 'OK' | 'WARNING' | 'ERROR'. Per-family issues escalate.
        messages: human-readable notes (banner text for the dashboard).
    """
    structure: Any                                # upm.bundle.io.StructureBundle
    parameters: dict[str, Any]                    # family -> upm.bundle.io.PackageBundle
    resolutions: dict[str, dict[str, Any]] = field(default_factory=dict)
    status: str = "OK"
    messages: list[str] = field(default_factory=list)


def _load_structure(entry: Entry):
    from upm.bundle.io import load_structure
    if entry.type != "structure":
        raise ValueError(f"{entry.ref()} is not a structure entry")
    return load_structure(entry.path)


def _load_param(entry: Entry):
    from upm.bundle.io import load_package
    return load_package(entry.path)


def _families_and_pins(structure_entry: Entry) -> list[tuple[str, str]]:
    return [(ref["name"], ref["version"]) for ref in structure_entry.parameterized_with]


def _finalize_status(result: PullResult) -> None:
    if any(r.get("status") == "ERROR" for r in result.resolutions.values()):
        result.status = "ERROR"
    elif any(r.get("status") == "WARNING" for r in result.resolutions.values()):
        result.status = "WARNING"
    else:
        result.status = "OK"


def pull_original(structure_entry: Entry) -> PullResult:
    """Return structure + exact pinned parameter versions."""
    result = PullResult(structure=_load_structure(structure_entry), parameters={})
    for family, version in _families_and_pins(structure_entry):
        entry = find_parameter_entry(family, version)
        if entry is None:
            result.resolutions[family] = {
                "status": "ERROR",
                "requested": version,
                "resolved": None,
                "message": f"pinned parameter entry {family}@{version} not found",
            }
            result.messages.append(
                f"original pin {family}@{version} is not discoverable in the library"
            )
            continue
        result.parameters[family] = _load_param(entry)
        result.resolutions[family] = {
            "status": "OK",
            "requested": version,
            "resolved": version,
            "renames_applied": {},
            "breaking_crossed": False,
            "message": f"original pin {family}@{version}",
        }
    _finalize_status(result)
    return result


def pull_version(structure_entry: Entry, family: str, version: str) -> PullResult:
    """Explicit version; fails loudly on compatibility ERROR (no fallback)."""
    result = PullResult(structure=_load_structure(structure_entry), parameters={})

    pinned_families = {fam for fam, _ in _families_and_pins(structure_entry)}
    if family not in pinned_families:
        # Still load all pinned families at their pin; override only the requested family.
        for fam, ver in _families_and_pins(structure_entry):
            entry = find_parameter_entry(fam, ver)
            if entry is not None:
                result.parameters[fam] = _load_param(entry)
                result.resolutions[fam] = {
                    "status": "OK", "requested": ver, "resolved": ver,
                    "renames_applied": {}, "breaking_crossed": False,
                    "message": f"original pin {fam}@{ver}",
                }
        # requested family not pinned — report
        result.resolutions[family] = {
            "status": "ERROR",
            "requested": version,
            "resolved": None,
            "message": f"structure is not parameterized with family {family!r}",
        }
        result.messages.append(result.resolutions[family]["message"])
        _finalize_status(result)
        return result

    # load pinned families other than the one being overridden
    for fam, ver in _families_and_pins(structure_entry):
        if fam == family:
            continue
        entry = find_parameter_entry(fam, ver)
        if entry is not None:
            result.parameters[fam] = _load_param(entry)
            result.resolutions[fam] = {
                "status": "OK", "requested": ver, "resolved": ver,
                "renames_applied": {}, "breaking_crossed": False,
                "message": f"original pin {fam}@{ver}",
            }

    # now attempt the specific requested version
    compat = compatibility_check(structure_entry, family, version)
    entry = find_parameter_entry(family, version)
    if compat.status == "ERROR" or entry is None:
        result.resolutions[family] = {
            "status": "ERROR",
            "requested": version,
            "resolved": None,
            "missing": compat.missing,
            "messages": compat.messages,
            "message": (
                f"cannot resolve {family}@{version}: " + "; ".join(compat.messages)
                if compat.messages else f"cannot resolve {family}@{version}"
            ),
        }
        result.messages.append(result.resolutions[family]["message"])
    else:
        result.parameters[family] = _load_param(entry)
        result.resolutions[family] = _compat_to_resolution(compat, version, version)
        if compat.status == "WARNING":
            result.messages.append(
                f"{family}@{version}: breaking change crossed in the version chain"
            )

    _finalize_status(result)
    return result


def pull_latest(structure_entry: Entry) -> PullResult:
    """Default pull. Newest non-deprecated compatible version per family.

    Fallback: if the latest version is incompatible (missing keys), walk
    backward until we find the newest compatible version. If all fail,
    return ERROR for that family.

    Honors ``lock_to_original``: returns :func:`pull_original` verbatim.
    """
    if structure_entry.lock_to_original:
        r = pull_original(structure_entry)
        for res in r.resolutions.values():
            res.setdefault("message", "")
            res["message"] = (res["message"] + " (locked to original)").strip()
        r.messages.insert(0, "structure is pinned by author; pull_latest returned the original")
        return r

    result = PullResult(structure=_load_structure(structure_entry), parameters={})
    family_versions_index = index_family_versions()

    for family, pin_version in _families_and_pins(structure_entry):
        fv = family_versions_index.get(family)
        if fv is None:
            result.resolutions[family] = {
                "status": "ERROR",
                "requested": "latest",
                "resolved": None,
                "message": f"no versions of family {family!r} found in library",
            }
            result.messages.append(result.resolutions[family]["message"])
            continue

        # Walk candidates from newest to oldest, skip deprecated.
        candidates = [e for e in fv.sorted_descending() if not e.deprecated]
        chosen_entry: Entry | None = None
        chosen_compat: CompatibilityResult | None = None
        tried: list[str] = []
        for candidate in candidates:
            tried.append(candidate.version)
            compat = compatibility_check(structure_entry, family, candidate.version)
            if compat.status != "ERROR":
                chosen_entry = candidate
                chosen_compat = compat
                break

        if chosen_entry is None or chosen_compat is None:
            result.resolutions[family] = {
                "status": "ERROR",
                "requested": "latest",
                "resolved": None,
                "tried": tried,
                "message": (
                    f"no compatible version of {family!r} found; tried "
                    + ", ".join(tried) if tried else f"no candidates for {family!r}"
                ),
            }
            result.messages.append(result.resolutions[family]["message"])
            continue

        result.parameters[family] = _load_param(chosen_entry)
        resolution = _compat_to_resolution(chosen_compat, "latest", chosen_entry.version)
        result.resolutions[family] = resolution

        if chosen_entry.version != pin_version:
            result.messages.append(
                f"{family}: resolved to {chosen_entry.version} "
                f"(original pin was {pin_version})"
            )
        if chosen_compat.status == "WARNING":
            result.messages.append(
                f"{family}@{chosen_entry.version}: breaking change crossed"
            )
        if chosen_compat.renames_applied:
            rn = chosen_compat.renames_applied
            result.messages.append(
                f"{family}: auto-renamed {len(rn)} atom type(s) "
                + ", ".join(f"{k}→{v}" for k, v in list(rn.items())[:4])
                + ("…" if len(rn) > 4 else "")
            )

        # If we fell back because latest was incompatible, surface that.
        if chosen_entry.version != candidates[0].version:
            result.messages.append(
                f"{family}: latest version {candidates[0].version} was incompatible; "
                f"returning {chosen_entry.version}"
            )

    _finalize_status(result)
    return result


def _compat_to_resolution(compat: CompatibilityResult, requested: str, resolved: str) -> dict[str, Any]:
    return {
        "status": compat.status,
        "requested": requested,
        "resolved": resolved,
        "renames_applied": dict(compat.renames_applied),
        "breaking_crossed": compat.breaking_crossed,
        "missing": dict(compat.missing),
        "messages": list(compat.messages),
        "message": (
            f"resolved {resolved}"
            + (f" (from requested {requested})" if requested != resolved else "")
        ),
    }


__all__ = [
    "PullResult",
    "pull_latest",
    "pull_original",
    "pull_version",
]
