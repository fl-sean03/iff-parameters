"""Download parameters in various formats."""
import streamlit as st

from utils.data import list_bundles, load_bundle_tables
from utils.export import export_tables_csv_zip, export_as_frc, export_as_prm

st.title("Download Parameters")

bundles = list_bundles()
names = [f"{e['name']}@{e['version']} ({e['format']})" for e in bundles]

selected_idx = st.selectbox("Select bundle:", range(len(names)), format_func=lambda i: names[i])
entry = bundles[selected_idx]
tables = load_bundle_tables(entry["path"])

st.markdown("---")

# Format selection
fmt = entry["format"]
format_options = ["CSV (ZIP)"]
if fmt == "cvff":
    format_options.insert(0, "CVFF (.frc)")
elif fmt == "charmm":
    format_options.insert(0, "CHARMM (.prm)")

selected_format = st.radio("Export format:", format_options)

# Table selection
st.subheader("Tables to include")
table_names = sorted(tables.keys())
selected_tables = {}
cols = st.columns(3)
for i, name in enumerate(table_names):
    with cols[i % 3]:
        if st.checkbox(f"{name} ({len(tables[name])} rows)", value=True, key=f"sel_{name}"):
            selected_tables[name] = tables[name]

st.markdown("---")

if not selected_tables:
    st.warning("Select at least one table to export.")
else:
    # Preview
    with st.expander("Preview (first 5 rows per table)"):
        for name, df in sorted(selected_tables.items()):
            st.caption(f"**{name}** ({len(df)} rows)")
            st.dataframe(df.head(5), use_container_width=True)

    # Generate and download
    base_name = entry["name"]

    if selected_format == "CSV (ZIP)":
        data = export_tables_csv_zip(selected_tables)
        st.download_button(
            "Download CSV ZIP",
            data=data,
            file_name=f"{base_name}.zip",
            mime="application/zip",
        )
    elif selected_format == "CVFF (.frc)":
        data = export_as_frc(selected_tables)
        st.download_button(
            "Download .frc",
            data=data,
            file_name=f"{base_name}.frc",
            mime="application/octet-stream",
        )
    elif selected_format == "CHARMM (.prm)":
        data = export_as_prm(selected_tables)
        st.download_button(
            "Download .prm",
            data=data,
            file_name=f"{base_name}.prm",
            mime="application/octet-stream",
        )
