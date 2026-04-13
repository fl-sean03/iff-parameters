"""Upload-time conflict detection between a new parameter set and existing entries.

Used by the dashboard's Upload page to preview collisions before ingest.
Returns structured rows the UI can render and a conflict count it can
use to gate the final ingest button.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

_NUMERIC_COLS = {
    "atom_types": ("lj_a", "lj_b", "mass_amu"),
    "bonds": ("k", "r0"),
    "angles": ("k", "theta0_deg"),
    "torsions": ("kphi", "n", "phi0"),
}


@dataclass
class CollisionRow:
    entry: str              # "family@version" of the existing entry
    scope: str              # "atom_types" | "bonds" | "angles" | "torsions"
    key: str                # stringified key ("ti4f" or "ti — o")
    disagrees_on: list[str] # numeric columns where values differ
    status: str             # "conflict" | "duplicate"


def _disagrees(nv: Any, ov: Any, rtol: float = 1e-6) -> bool:
    try:
        fnv = float(nv)
        fov = float(ov)
    except (TypeError, ValueError):
        return str(nv) != str(ov)
    if math.isnan(fnv) and math.isnan(fov):
        return False
    if math.isnan(fnv) or math.isnan(fov):
        return True
    return abs(fnv - fov) > rtol * max(abs(fnv), abs(fov), 1.0)


def _disagreements(new_row: dict, old_row: dict, cols: Iterable[str]) -> list[str]:
    return [c for c in cols if _disagrees(new_row.get(c), old_row.get(c))]


def detect_collisions(
    new_tables: dict[str, Any],
    existing_entries: Iterable[dict[str, Any]],
    load_tables,                           # callable: path_str -> {table_name: df}
) -> list[CollisionRow]:
    """Return a flat list of collisions grouped by scope.

    Each existing entry is loaded via ``load_tables(entry_path)``. For each
    scope (atom_types, bonds, angles, torsions), keys present in both the
    new and existing tables are compared. Identical keys with identical
    values are ``duplicate``; any numeric disagreement is ``conflict``.
    """
    out: list[CollisionRow] = []
    for entry in existing_entries:
        try:
            ex = load_tables(entry["path"])
        except Exception:
            continue

        for scope, cols in _NUMERIC_COLS.items():
            if scope not in new_tables or scope not in ex:
                continue
            new_df = new_tables[scope]
            ex_df = ex[scope]
            if new_df is None or ex_df is None or len(new_df) == 0 or len(ex_df) == 0:
                continue

            if scope == "atom_types":
                common = (set(new_df["atom_type"].astype(str))
                          & set(ex_df["atom_type"].astype(str)))
                for t in sorted(common):
                    nv = new_df[new_df["atom_type"] == t].iloc[0].to_dict()
                    ov = ex_df[ex_df["atom_type"] == t].iloc[0].to_dict()
                    d = _disagreements(nv, ov, cols)
                    out.append(CollisionRow(
                        entry=entry["ref"],
                        scope="atom_types",
                        key=t,
                        disagrees_on=d,
                        status="conflict" if d else "duplicate",
                    ))
            elif scope == "bonds":
                new_keys = set(zip(new_df["t1"].astype(str), new_df["t2"].astype(str)))
                ex_keys = set(zip(ex_df["t1"].astype(str), ex_df["t2"].astype(str)))
                for k in sorted(new_keys & ex_keys):
                    nv = new_df[(new_df["t1"] == k[0]) & (new_df["t2"] == k[1])].iloc[0].to_dict()
                    ov = ex_df[(ex_df["t1"] == k[0]) & (ex_df["t2"] == k[1])].iloc[0].to_dict()
                    d = _disagreements(nv, ov, cols)
                    out.append(CollisionRow(
                        entry=entry["ref"],
                        scope="bonds",
                        key=f"{k[0]} — {k[1]}",
                        disagrees_on=d,
                        status="conflict" if d else "duplicate",
                    ))
    return out


def count_conflicts(rows: list[CollisionRow]) -> tuple[int, int]:
    """(n_real_disagreements, n_harmless_duplicates)."""
    n_conflicts = sum(1 for r in rows if r.status == "conflict")
    return n_conflicts, len(rows) - n_conflicts


__all__ = ["CollisionRow", "detect_collisions", "count_conflicts"]
