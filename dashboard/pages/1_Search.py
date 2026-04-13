"""Search across parameter sets and structures."""
import streamlit as st

from utils.data import (
    get_all_atom_types,
    list_parameter_entries,
    list_structure_entries,
)

st.title("Search")

tab_atoms, tab_material, tab_family = st.tabs([
    "Atom type",
    "Material",
    "Parameter family",
])

# -------------------------------- Atom type --------------------------------
with tab_atoms:
    query = st.text_input("Search atom types across all parameter entries:",
                          placeholder="e.g., ti4f, oc23, sc4, hoy")
    if query:
        all_types = get_all_atom_types()
        if len(all_types) == 0:
            st.warning("No atom types in the library yet.")
        else:
            mask = all_types["atom_type"].str.contains(query, case=False, na=False)
            results = all_types[mask]
            if len(results) == 0:
                st.info(f"No atom types matching '{query}'.")
            else:
                st.success(
                    f"Found **{len(results)}** match(es) across "
                    f"**{results['bundle'].nunique()}** parameter set(s)"
                )
                cols = [c for c in
                        ["atom_type", "element", "mass_amu", "lj_a", "lj_b",
                         "bundle", "version", "format"]
                        if c in results.columns]
                st.dataframe(results[cols].sort_values(["atom_type", "bundle"]),
                             use_container_width=True, height=420)
                st.download_button("Download results as CSV",
                                   results[cols].to_csv(index=False),
                                   f"search_{query}.csv", "text/csv")

# -------------------------------- Material ---------------------------------
with tab_material:
    params = list_parameter_entries()
    structs = list_structure_entries()

    # Materials universe = union of provenance.materials + structure material_class
    materials = set()
    for e in params:
        for m in e.get("materials", []):
            materials.add(str(m))
    for s in structs:
        for m in s.get("materials", []):
            materials.add(str(m))
        materials.add(s.get("material_class", ""))
    materials.discard("")
    selected = st.multiselect("Select material(s):", sorted(materials))

    if selected:
        sel_low = [s.lower() for s in selected]

        matching_params = [
            e for e in params
            if any(any(s in m.lower() for m in e.get("materials", [])) for s in sel_low)
        ]
        matching_structs = [
            s for s in structs
            if (any(s_low in s.get("material_class", "").lower() for s_low in sel_low)
                or any(any(sel in m.lower() for m in s.get("materials", []))
                       for sel in sel_low))
        ]

        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"Parameter sets ({len(matching_params)})")
            if matching_params:
                for entry in matching_params:
                    st.write(f"- **`{entry['ref']}`** ({entry['format'].upper()})"
                             f" — {', '.join(entry['materials']) or '—'}")
            else:
                st.info("No matching parameter sets.")
        with c2:
            st.subheader(f"Structures ({len(matching_structs)})")
            if matching_structs:
                # Show grouped by material class
                by_class: dict[str, list] = {}
                for s in matching_structs:
                    by_class.setdefault(s["material_class"], []).append(s)
                for cls, items in sorted(by_class.items()):
                    with st.expander(f"{cls} ({len(items)})"):
                        for s in items[:30]:
                            st.write(f"- `{s['name']}@{s['version']}` "
                                     f"({s['n_atoms']} atoms → {s['atom_type_family']})")
                        if len(items) > 30:
                            st.caption(f"… and {len(items) - 30} more")
            else:
                st.info("No matching structures.")

# ------------------------- Parameter family --------------------------------
with tab_family:
    params = list_parameter_entries()
    families = sorted({e["name"] for e in params})
    if not families:
        st.info("No parameter entries.")
    else:
        fam = st.selectbox("Family:", families)
        # All versions of this family
        versions = [e for e in params if e["name"] == fam]
        st.write(f"**{len(versions)} version(s) of `{fam}`:**")
        for v in versions:
            badges = []
            if v.get("partial_roundtrip"):
                badges.append("⚠ partial roundtrip")
            if v.get("deprecated"):
                badges.append("🚫 deprecated")
            badge_str = "  ".join(badges)
            st.write(f"- `{v['ref']}`  {badge_str}")
        # Structures parameterized against any version of this family
        consumers = [
            s for s in list_structure_entries()
            if s.get("atom_type_family") == fam
        ]
        st.write(f"**{len(consumers)} structure(s) using this family:**")
        for s in consumers[:50]:
            pinned = ", ".join(p["version"] for p in s.get("parameterized_with", []))
            st.write(f"- `{s['material_class']}/{s['name']}@{s['version']}` "
                     f"→ pinned to {pinned}")
        if len(consumers) > 50:
            st.caption(f"… and {len(consumers) - 50} more")
