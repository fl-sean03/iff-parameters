"""Coverage page: materials x parameter family matrix, stale/gap detection."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data import list_parameter_entries, list_structure_entries

st.title("Coverage")
st.caption(
    "Materials × parameter family matrix. Cells show entry counts + newest version. "
    "Empty cells are gaps; stale cells flagged for review."
)

params = list_parameter_entries()
structs = list_structure_entries()

# Collect material universe from both parameter and structure entries
materials: set[str] = set()
for e in params:
    for m in e.get("materials", []):
        materials.add(str(m))
for s in structs:
    for m in s.get("materials", []):
        materials.add(str(m))
    materials.add(s.get("material_class", ""))
materials.discard("")
materials = sorted(materials)

# Families (parameter family names only)
families = sorted({e["name"] for e in params})

if not materials or not families:
    st.info("Not enough data for coverage grid yet.")
    st.stop()

# Build the grid as a DataFrame of cell objects
def _cell_label(mat: str, fam: str) -> str:
    # Count parameter entries for family fam that cover material mat
    p_hits = [e for e in params if e["name"] == fam
              and mat in e.get("materials", [])]
    s_hits = [s for s in structs
              if s.get("atom_type_family") == fam
              and (mat == s.get("material_class") or mat in s.get("materials", []))]
    parts = []
    if p_hits:
        latest_v = sorted(e["version"] for e in p_hits)[-1]
        parts.append(f"P:{len(p_hits)}@{latest_v}")
    if s_hits:
        parts.append(f"S:{len(s_hits)}")
    return " / ".join(parts) if parts else "—"


rows = []
for mat in materials:
    row = {"Material": mat}
    for fam in families:
        row[fam] = _cell_label(mat, fam)
    rows.append(row)

grid_df = pd.DataFrame(rows)
st.subheader("Coverage grid")
st.caption("Cell format: `P:<param-entry-count>@<latest-version> / S:<structure-count>`. `—` = gap.")
st.dataframe(grid_df, use_container_width=True, hide_index=True, height=400)

# Text summary of gaps
gaps = []
for mat in materials:
    for fam in families:
        p_hits = [e for e in params if e["name"] == fam and mat in e.get("materials", [])]
        s_hits = [s for s in structs
                  if s.get("atom_type_family") == fam and mat == s.get("material_class")]
        if not p_hits and not s_hits:
            gaps.append({"Material": mat, "Family": fam})

if gaps:
    with st.expander(f"Gaps ({len(gaps)} empty cells)"):
        st.dataframe(pd.DataFrame(gaps), use_container_width=True, hide_index=True)

# Material → structures breakdown
st.subheader("Structures per material class")
if structs:
    counts = {}
    for s in structs:
        counts[s["material_class"]] = counts.get(s["material_class"], 0) + 1
    counts_df = pd.DataFrame(
        [{"Material class": k, "Structures": v} for k, v in sorted(counts.items())]
    )
    st.bar_chart(counts_df, x="Material class", y="Structures")
