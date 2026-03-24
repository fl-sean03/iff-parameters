"""Compare two force field bundles side-by-side."""
import streamlit as st
import pandas as pd

from utils.data import list_bundles, load_bundle_tables

st.title("Compare Bundles")

bundles = list_bundles()
names = [f"{e['name']}@{e['version']}" for e in bundles]

col1, col2 = st.columns(2)
with col1:
    idx_a = st.selectbox("Bundle A:", range(len(names)), format_func=lambda i: names[i], key="cmp_a")
with col2:
    idx_b = st.selectbox("Bundle B:", range(len(names)), index=min(1, len(names) - 1), format_func=lambda i: names[i], key="cmp_b")

if idx_a == idx_b:
    st.info("Select two different bundles to compare.")
else:
    tables_a = load_bundle_tables(bundles[idx_a]["path"])
    tables_b = load_bundle_tables(bundles[idx_b]["path"])

    from upm.registry.diff import diff_tables
    diff = diff_tables(tables_a, tables_b)

    # Summary metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Added Types", f"+{len(diff.added_types)}")
    c2.metric("Removed Types", f"-{len(diff.removed_types)}")
    c3.metric("Changed Params", f"~{len(diff.changed_params)}")

    st.markdown("---")

    # Details
    tab1, tab2, tab3 = st.tabs(["Added Types", "Removed Types", "Changed Parameters"])

    with tab1:
        if diff.added_types:
            st.write(f"Types in **{names[idx_b]}** but not in **{names[idx_a]}**:")
            for chunk in [diff.added_types[i:i + 8] for i in range(0, len(diff.added_types), 8)]:
                st.write(", ".join(f"`{t}`" for t in chunk))
        else:
            st.info("No added types.")

    with tab2:
        if diff.removed_types:
            st.write(f"Types in **{names[idx_a]}** but not in **{names[idx_b]}**:")
            for chunk in [diff.removed_types[i:i + 8] for i in range(0, len(diff.removed_types), 8)]:
                st.write(", ".join(f"`{t}`" for t in chunk))
        else:
            st.info("No removed types.")

    with tab3:
        if diff.changed_params:
            rows = [{"atom_type": c.key, "field": c.field,
                     f"{names[idx_a]}": c.old_value, f"{names[idx_b]}": c.new_value}
                    for c in diff.changed_params]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=400)
        else:
            st.info("No changed parameters.")

    st.markdown("---")
    st.text(diff.summary())
