"""Conflicts page: cross-entry key collisions with value disagreements."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data import get_data_dir

st.title("Conflicts")
st.caption(
    "Cross-entry key collisions where two parameter sets disagree on numeric "
    "values. Identical duplicates are filtered out; pairs of intra-family "
    "versions (v1.0 vs v1.1) are not conflicts by design."
)

# Load all parameter entries via UPM's discovery + PackageIndex
from upm.registry.discovery import discover_local_packages
from upm.registry.index import PackageIndex


@st.cache_data(ttl=60)
def _load_index_summary() -> tuple[list[dict], dict]:
    # Discovery scans the live data_dir; we must restrict to parameter entries
    # (structure entries also have manifest.json but carry no FF tables).
    data_dir = Path(get_data_dir())
    packages = discover_local_packages(data_dir / "parameters")
    # Collapse intra-family versions: only take the latest non-deprecated per name.
    latest: dict[str, any] = {}
    for p in packages:
        current = latest.get(p.name)
        if current is None:
            latest[p.name] = p
        else:
            # pick the one whose version sorts higher
            def _key(pkg):
                return pkg.version
            if _key(p) > _key(current):
                latest[p.name] = p
    pkgs = list(latest.values())

    idx = PackageIndex(pkgs)
    conflicts = idx.conflicts()

    # serialize into DataFrame-friendly rows
    rows = []
    for c in conflicts:
        rows.append({
            "Scope": c.scope,
            "Key": " — ".join(c.key) if isinstance(c.key, tuple) else str(c.key),
            "Disagrees on": ", ".join(c.disagreements),
            "Entries": ", ".join(f"{o.package_name}@{o.package_version}" for o in c.occurrences),
            "Count": len(c.occurrences),
        })
    summary = {
        "n_entries": len(pkgs),
        "n_conflicts": len(conflicts),
        "by_scope": {},
    }
    for c in conflicts:
        summary["by_scope"][c.scope] = summary["by_scope"].get(c.scope, 0) + 1
    return rows, summary


rows, summary = _load_index_summary()

c1, c2, c3 = st.columns(3)
c1.metric("Entries indexed", summary["n_entries"])
c2.metric("Total conflicts", summary["n_conflicts"])
by_scope = summary.get("by_scope", {})
c3.metric("Scopes with conflicts", len(by_scope))

if by_scope:
    bc_df = pd.DataFrame(
        [{"Scope": k, "Count": v} for k, v in sorted(by_scope.items())]
    )
    st.bar_chart(bc_df, x="Scope", y="Count")

if not rows:
    st.success("No cross-entry conflicts detected in the library.")
    st.stop()

df = pd.DataFrame(rows).sort_values(["Scope", "Count"], ascending=[True, False])

scope_filter = st.multiselect(
    "Filter by scope:", sorted(df["Scope"].unique()),
    default=sorted(df["Scope"].unique()),
)
key_filter = st.text_input("Filter by key substring:", placeholder="e.g. ti4f")

view = df[df["Scope"].isin(scope_filter)]
if key_filter:
    view = view[view["Key"].str.contains(key_filter, case=False, regex=False)]

st.caption(f"Showing {len(view)} conflicts")
st.dataframe(view, use_container_width=True, hide_index=True, height=500)

st.download_button(
    "Download conflicts.csv",
    df.to_csv(index=False),
    "iff_conflicts.csv",
    "text/csv",
)
