"""Search force field parameters across all bundles."""
import streamlit as st

from utils.data import get_all_atom_types, list_bundles

st.title("Search Parameters")

tab1, tab2 = st.tabs(["Atom Type Search", "Material Search"])

# --- Atom Type Search ---
with tab1:
    query = st.text_input("Search atom types:", placeholder="e.g., Au, c3, si, hoy")

    if query:
        all_types = get_all_atom_types()
        if len(all_types) == 0:
            st.warning("No atom types found in any bundle.")
        else:
            mask = all_types["atom_type"].str.contains(query, case=False, na=False)
            results = all_types[mask]

            if len(results) == 0:
                st.info(f"No atom types matching '{query}'.")
            else:
                st.success(f"Found {len(results)} result(s) across {results['bundle'].nunique()} bundle(s)")

                display_cols = ["atom_type", "element", "mass_amu", "lj_a", "lj_b", "bundle", "format"]
                available_cols = [c for c in display_cols if c in results.columns]
                st.dataframe(
                    results[available_cols].sort_values(["atom_type", "bundle"]),
                    use_container_width=True,
                    height=400,
                )

                csv = results[available_cols].to_csv(index=False)
                st.download_button("Download results as CSV", csv, f"search_{query}.csv", "text/csv")

# --- Material Search ---
with tab2:
    bundles = list_bundles()
    all_materials = sorted({m for e in bundles for m in e.get("materials", [])})

    selected = st.multiselect("Select materials:", all_materials)

    if selected:
        matching = []
        for entry in bundles:
            entry_mats = set(m.lower() for m in entry.get("materials", []))
            if any(s.lower() in entry_mats for s in selected):
                matching.append(entry)

        if matching:
            st.success(f"{len(matching)} bundle(s) cover selected materials")
            for entry in matching:
                st.write(f"- **{entry['name']}** ({entry['format'].upper()}) — {', '.join(entry['materials'])}")
        else:
            st.info("No bundles match the selected materials.")
