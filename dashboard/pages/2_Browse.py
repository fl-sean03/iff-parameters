"""Browse detailed parameter tables for a specific bundle."""
import streamlit as st
import pandas as pd

from utils.data import list_bundles, load_bundle_tables, load_manifest

st.title("Browse Parameters")

bundles = list_bundles()
bundle_names = [f"{e['name']}@{e['version']} ({e['format']})" for e in bundles]

selected_idx = st.selectbox("Select bundle:", range(len(bundle_names)), format_func=lambda i: bundle_names[i])
entry = bundles[selected_idx]
tables = load_bundle_tables(entry["path"])
manifest = load_manifest(entry["path"])

# Bundle info
prov = manifest.get("provenance", {})
cols = st.columns(3)
cols[0].write(f"**Author:** {prov.get('author', 'Unknown')}")
cols[1].write(f"**Format:** {entry['format'].upper()}")
doi = prov.get("publication_doi")
if doi:
    cols[2].write(f"**DOI:** [{doi}](https://doi.org/{doi})")
else:
    cols[2].write("**DOI:** —")

materials = prov.get("materials", [])
if materials:
    st.write(f"**Materials:** {', '.join(materials)}")

st.markdown("---")

# Tabs for each table type
table_names = sorted(tables.keys())
if not table_names:
    st.warning("No tables found in this bundle.")
else:
    tabs = st.tabs([f"{name} ({len(tables[name])})" for name in table_names])

    for tab, name in zip(tabs, table_names):
        with tab:
            df = tables[name]

            # Filter
            filter_col = st.columns([3, 1])
            with filter_col[0]:
                text_filter = st.text_input(f"Filter {name}:", key=f"filter_{name}", placeholder="Type to filter...")
            with filter_col[1]:
                st.write(f"**{len(df)} rows**")

            if text_filter:
                mask = df.apply(lambda row: row.astype(str).str.contains(text_filter, case=False).any(), axis=1)
                df = df[mask]
                st.caption(f"Showing {len(df)} filtered rows")

            st.dataframe(df, use_container_width=True, height=500)

            csv = df.to_csv(index=False)
            st.download_button(f"Download {name}.csv", csv, f"{entry['name']}_{name}.csv", "text/csv", key=f"dl_{name}")
