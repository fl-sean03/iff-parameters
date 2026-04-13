"""Browse parameter sets and structures with cross-links."""
import streamlit as st

from utils.data import (
    list_parameter_entries, list_structure_entries,
    load_bundle_tables, load_manifest, load_structure_atoms,
    load_structure_geometry_text,
)

st.title("Browse")

tabs = st.tabs(["Parameters", "Structures"])

# -------------------------------- Parameters --------------------------------
with tabs[0]:
    bundles = list_parameter_entries()
    if not bundles:
        st.info("No parameter entries. Run the seed script.")
        st.stop()

    labels = [
        f"{e['ref']} ({e['format']})" + (" ⚠" if e.get('partial_roundtrip') else "")
        + (" 🚫" if e.get('deprecated') else "")
        for e in bundles
    ]
    idx = st.selectbox("Select parameter set:", range(len(labels)),
                       format_func=lambda i: labels[i], key="param_select")
    entry = bundles[idx]
    tables = load_bundle_tables(entry["path"])
    manifest = load_manifest(entry["path"])

    prov = manifest.get("provenance", {})
    cols = st.columns(4)
    cols[0].write(f"**Author:** {prov.get('author', '—')}")
    cols[1].write(f"**Format:** {entry['format'].upper()}")
    doi = prov.get("publication_doi")
    cols[2].write(f"**DOI:** [{doi}](https://doi.org/{doi})" if doi else "**DOI:** —")
    cols[3].write(f"**Partial:** {'yes' if entry.get('partial_roundtrip') else 'no'}")

    if manifest.get("supersedes"):
        st.write(f"**Supersedes:** `{manifest['supersedes']}`")
    if manifest.get("parent_ff"):
        st.write(f"**Parent FF:** `{manifest['parent_ff']}`")
    if manifest.get("deprecated"):
        st.warning(f"This version is deprecated: {manifest.get('deprecation_reason', '—')}")
    if prov.get("notes"):
        st.caption(prov["notes"])

    # Structures using this parameter entry
    all_structures = list_structure_entries()
    consumers = [
        s for s in all_structures
        if any(r.get("name") == entry["name"] and r.get("version") == entry["version"]
               for r in s.get("parameterized_with", []))
    ]
    if consumers:
        with st.expander(f"Structures parameterized with this version ({len(consumers)})"):
            for s in consumers:
                st.write(f"- `{s['material_class']}/{s['name']}@{s['version']}` — {s['n_atoms']} atoms")

    st.markdown("---")

    # Tables
    table_names = sorted(tables.keys())
    if not table_names:
        st.warning("No tables in this entry.")
    else:
        table_tabs = st.tabs([f"{n} ({len(tables[n])})" for n in table_names])
        for tab, name in zip(table_tabs, table_names):
            with tab:
                df = tables[name]
                fcol = st.columns([3, 1])
                filt = fcol[0].text_input(f"Filter {name}:", key=f"filter_{name}",
                                           placeholder="Type to filter…")
                fcol[1].write(f"**{len(df)} rows**")
                view = df
                if filt:
                    mask = df.apply(
                        lambda r: r.astype(str).str.contains(filt, case=False).any(), axis=1
                    )
                    view = df[mask]
                    st.caption(f"Showing {len(view)} filtered rows")
                st.dataframe(view, use_container_width=True, height=500)
                st.download_button(
                    f"Download {name}.csv",
                    view.to_csv(index=False),
                    f"{entry['name']}_{entry['version']}_{name}.csv",
                    "text/csv",
                    key=f"dl_{name}",
                )

# -------------------------------- Structures --------------------------------
with tabs[1]:
    structs = list_structure_entries()
    if not structs:
        st.info("No structures. Run scripts/seed_from_interface_ff15_structures.py.")
        st.stop()

    classes = sorted({s["material_class"] for s in structs})
    sel_class = st.selectbox("Material class:", classes, key="class_select")

    in_class = [s for s in structs if s["material_class"] == sel_class]
    labels = [f"{s['name']}@{s['version']}  ({s['n_atoms']} atoms → {s['atom_type_family']})"
              for s in in_class]
    idx = st.selectbox("Structure:", range(len(labels)),
                       format_func=lambda i: labels[i], key="struct_select")
    s = in_class[idx]

    # Summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Atoms", s["n_atoms"])
    c2.metric("Family", s.get("atom_type_family", "—"))
    pins = s.get("parameterized_with", [])
    c3.metric("Pinned versions", ", ".join(f"{p['version']}" for p in pins) or "—")

    if s.get("lock_to_original"):
        st.warning("This structure is locked to its original parameters (pull_latest disabled).")

    # Pinned parameters
    with st.expander("Pinned parameter set(s) — original pin"):
        for ref in pins:
            st.write(f"- `{ref['name']}@{ref['version']}`")

    # Atoms table
    atoms = load_structure_atoms(s["path"])
    st.subheader(f"Atoms ({len(atoms)})")
    st.dataframe(atoms.head(200), use_container_width=True, height=300)
    if len(atoms) > 200:
        st.caption(f"Showing first 200 of {len(atoms)} — download full CSV below.")
    st.download_button(
        "Download atoms.csv",
        atoms.to_csv(index=False),
        f"{s['name']}_{s['version']}_atoms.csv",
        "text/csv",
        key="dl_atoms",
    )

    # Raw geometry (collapsed)
    with st.expander("Raw geometry source (.car)"):
        txt = load_structure_geometry_text(s["path"])
        st.code(txt[:4000] + ("…\n[truncated]\n" if len(txt) > 4000 else ""), language=None)
