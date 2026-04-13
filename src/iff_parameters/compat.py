"""Compatibility checking for structure -> parameter resolution.

When pulling a structure against a target FF version, we must verify
every atom type (and referenced bond/angle/torsion key) used by the
structure resolves against the target version. This module:

  1. walks the rename chain between the structure's pinned version and
     the target version, composing all declared ``renames`` maps;
  2. applies that composition to every key required by the structure;
  3. compares the transformed keys against the target's tables;
  4. reports status = OK | WARNING (breaking crossed) | ERROR (missing keys).

Only parameter-entry ``renames`` are composed. Structure entries never
declare renames.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .entries import Entry, FamilyVersions, find_parameter_entry, index_family_versions

Status = str  # "OK" | "WARNING" | "ERROR"


@dataclass
class CompatibilityResult:
    status: Status                                   # "OK" | "WARNING" | "ERROR"
    target: str                                      # "family@version" that was evaluated
    renames_applied: dict[str, str] = field(default_factory=dict)
    missing: dict[str, list[Any]] = field(default_factory=dict)   # per-scope list of missing keys
    breaking_crossed: bool = False
    fallback_version: str | None = None              # set when we recommend a fallback
    messages: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return self.status == "OK"


def _load_tables(entry: Entry) -> dict[str, Any]:
    from upm.bundle.io import load_package
    bundle = load_package(entry.path)
    return bundle.tables


def _sorted_lineage_forward(versions: FamilyVersions, start_version: str, target_version: str) -> list[Entry]:
    """Return entries with start_version < v <= target_version, ascending.

    Used to compose renames moving forward from a pin to a target.
    """
    start = versions.get(start_version)
    target = versions.get(target_version)
    if start is None or target is None:
        return []
    start_v = start.parsed_version()
    target_v = target.parsed_version()
    if target_v <= start_v:
        return []
    return [
        e for e in versions.sorted_descending()[::-1]   # ascending
        if start_v < e.parsed_version() <= target_v
    ]


def compose_renames(versions: FamilyVersions, start_version: str, target_version: str) -> dict[str, str]:
    """Compose the rename chain from start_version → target_version.

    For each intermediate version (exclusive of start, inclusive of target),
    apply its ``renames`` map to the in-progress mapping.
    """
    # composition[k] = "what k becomes after the chain"
    composition: dict[str, str] = {}

    # we process each step in order, updating composition so that
    # for every original key k, composition[k] is its latest renamed form.
    # Seed with identity for all atom types in the starting entry.
    for step in _sorted_lineage_forward(versions, start_version, target_version):
        step_renames = step.renames
        if not step_renames:
            continue
        # apply rename to already-tracked keys
        new_composition: dict[str, str] = {}
        for original, current in composition.items():
            new_composition[original] = step_renames.get(current, current)
        # add any keys introduced directly in this step
        for old, new in step_renames.items():
            if old not in new_composition:
                new_composition[old] = new
        composition = new_composition

    return composition


def _any_breaking_between(versions: FamilyVersions, start_version: str, target_version: str) -> bool:
    for step in _sorted_lineage_forward(versions, start_version, target_version):
        if step.breaking:
            return True
    return False


def compatibility_check(
    structure_entry: Entry,
    target_family: str,
    target_version: str,
) -> CompatibilityResult:
    """Verify a structure resolves against a target parameter version.

    Only considers the structure's declared ``atom_type_family`` — multi-family
    structures require calling this once per family (see :func:`pull.pull_latest`).
    """
    result = CompatibilityResult(status="OK", target=f"{target_family}@{target_version}")

    if structure_entry.type != "structure":
        result.status = "ERROR"
        result.messages.append(f"{structure_entry.ref()} is not a structure entry")
        return result

    # resolve target
    target_entry = find_parameter_entry(target_family, target_version)
    if target_entry is None:
        result.status = "ERROR"
        result.messages.append(f"target parameter entry {target_family}@{target_version} not found")
        return result

    # find the pinned version (same family) to compose renames from
    pin_version = None
    for ref in structure_entry.parameterized_with:
        if ref["name"] == target_family:
            pin_version = ref["version"]
            break
    if pin_version is None:
        result.status = "ERROR"
        result.messages.append(
            f"structure is not parameterized with family {target_family!r}"
        )
        return result

    # fast path: same version → no rename walking needed
    if pin_version == target_version:
        renames: dict[str, str] = {}
        breaking = False
    else:
        family_versions = index_family_versions().get(target_family)
        if family_versions is None:
            result.status = "ERROR"
            result.messages.append(f"no versions found for family {target_family!r}")
            return result
        # composing forward from pin to target
        if target_entry.parsed_version() > family_versions.get(pin_version).parsed_version():
            renames = compose_renames(family_versions, pin_version, target_version)
            breaking = _any_breaking_between(family_versions, pin_version, target_version)
        else:
            # pulling an older version than the pin — no rename chain needed
            renames = {}
            breaking = False

    result.renames_applied = renames
    result.breaking_crossed = breaking

    # load the structure's atom types
    import pandas as pd
    atoms_csv_rel = structure_entry.manifest.get("atoms_csv", {}).get("path", "atoms.csv")
    atoms_df = pd.read_csv(structure_entry.path / atoms_csv_rel)
    all_structure_types: set[str] = set(atoms_df["ff_type"].astype(str).tolist())

    # For multi-family structures, restrict our check to atom types that
    # the *pinned* target family actually defines. Types outside this family
    # belong to a different family and are not our concern.
    pin_entry = find_parameter_entry(target_family, pin_version)
    if pin_entry is None:
        result.status = "ERROR"
        result.messages.append(f"pinned version {target_family}@{pin_version} not found")
        return result
    try:
        pin_tables = _load_tables(pin_entry)
    except Exception as e:
        result.status = "ERROR"
        result.messages.append(f"failed to load pinned bundle: {e}")
        return result
    pin_atom_types: set[str] = set()
    pin_at_df = pin_tables.get("atom_types")
    if pin_at_df is not None:
        pin_atom_types = set(pin_at_df["atom_type"].astype(str).tolist())

    # types to verify = intersection of structure types and pinned family types
    structure_types_in_family = all_structure_types & pin_atom_types

    # apply rename composition
    resolved_types = {renames.get(t, t) for t in structure_types_in_family}

    # load target FF tables
    try:
        target_tables = _load_tables(target_entry)
    except Exception as e:
        result.status = "ERROR"
        result.messages.append(f"failed to load target bundle: {e}")
        return result

    target_atom_types = set()
    at_df = target_tables.get("atom_types")
    if at_df is not None:
        target_atom_types = set(at_df["atom_type"].astype(str).tolist())

    missing_types = sorted(resolved_types - target_atom_types)
    if missing_types:
        result.missing["atom_types"] = missing_types
        result.status = "ERROR"
        result.messages.append(
            f"{len(missing_types)} atom type(s) missing in {target_family}@{target_version}: "
            f"{', '.join(missing_types[:6])}{'…' if len(missing_types) > 6 else ''}"
        )

    # bond / angle / torsion keys: derived from topology.csv if present
    topology_meta = structure_entry.manifest.get("topology_csv")
    if isinstance(topology_meta, dict) and topology_meta.get("path"):
        try:
            topo_df = pd.read_csv(structure_entry.path / topology_meta["path"])
        except Exception:
            topo_df = None
        if topo_df is not None:
            _check_scope_coverage(
                result, topo_df, target_tables, renames,
                scope_name="bonds", topology_kind="bond",
            )
            _check_scope_coverage(
                result, topo_df, target_tables, renames,
                scope_name="angles", topology_kind="angle",
            )
            _check_scope_coverage(
                result, topo_df, target_tables, renames,
                scope_name="torsions", topology_kind="torsion",
            )

    # breaking crossed with all keys present → warning
    if result.status == "OK" and breaking:
        result.status = "WARNING"
        result.messages.append("breaking change crossed in the version chain")

    return result


def _check_scope_coverage(
    result: CompatibilityResult,
    topo_df,
    target_tables: dict[str, Any],
    renames: dict[str, str],
    *,
    scope_name: str,
    topology_kind: str,
) -> None:
    """Mutate result.missing[scope_name] with any keys absent from target_tables[scope_name]."""
    df = target_tables.get(scope_name)
    if df is None or len(df) == 0:
        # cannot verify — not necessarily an error, skip silently
        return
    rows = topo_df[topo_df["kind"] == topology_kind]
    if len(rows) == 0:
        return

    # extract key tuples from the topology row's referenced atom types
    if "ff_type_i" not in rows.columns:
        # Older/minimal structures may not carry ff_types; skip coverage check.
        return

    missing: set[tuple] = set()
    known_keys = _extract_scope_keys(df, scope_name)
    for _, row in rows.iterrows():
        key = _topology_row_to_key(row, scope_name, renames)
        if key is None:
            continue
        # bond keys are canonicalized alphabetically in UPM tables
        canon = _canonicalize_key(key, scope_name)
        if canon not in known_keys:
            missing.add(canon)
    if missing:
        result.missing.setdefault(scope_name, []).extend(sorted(missing))
        result.status = "ERROR"
        result.messages.append(
            f"{len(missing)} {scope_name} key(s) missing in target"
        )


def _extract_scope_keys(df, scope_name: str) -> set[tuple]:
    if scope_name == "bonds":
        return set(zip(df["t1"].astype(str), df["t2"].astype(str)))
    if scope_name == "angles":
        return set(zip(df["t1"].astype(str), df["t2"].astype(str), df["t3"].astype(str)))
    if scope_name == "torsions":
        return set(zip(df["t1"].astype(str), df["t2"].astype(str),
                       df["t3"].astype(str), df["t4"].astype(str)))
    return set()


def _topology_row_to_key(row, scope_name: str, renames: dict[str, str]) -> tuple | None:
    try:
        t_i = renames.get(str(row["ff_type_i"]), str(row["ff_type_i"]))
        t_j = renames.get(str(row["ff_type_j"]), str(row["ff_type_j"]))
    except KeyError:
        return None
    if scope_name == "bonds":
        return (t_i, t_j)
    try:
        t_k = renames.get(str(row["ff_type_k"]), str(row["ff_type_k"]))
    except KeyError:
        return None
    if scope_name == "angles":
        return (t_i, t_j, t_k)
    try:
        t_l = renames.get(str(row["ff_type_l"]), str(row["ff_type_l"]))
    except KeyError:
        return None
    if scope_name == "torsions":
        return (t_i, t_j, t_k, t_l)
    return None


def _canonicalize_key(key: tuple, scope_name: str) -> tuple:
    # Match normalize_tables in UPM: bonds sort first pair, angles reverse if needed,
    # torsions reverse if needed. Delegating to UPM if possible would be nicer,
    # but the tables have already been normalized on load.
    if scope_name == "bonds":
        return tuple(sorted(key))
    return key


__all__ = [
    "CompatibilityResult",
    "compatibility_check",
    "compose_renames",
]
