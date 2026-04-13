"""IFF Parameters Browser — Heinz Lab central library (v0.2)."""
import streamlit as st

st.set_page_config(
    page_title="IFF Parameters Browser",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.data import (
    get_library_stats,
    list_parameter_entries,
    list_structure_entries,
)

# --- Sidebar ---
st.sidebar.title("IFF Parameters")
st.sidebar.caption("Heinz Lab, CU Boulder")
st.sidebar.markdown("---")
st.sidebar.info(
    "Central library of force field parameters and "
    "pre-parameterized structures.\n\n"
    "[GitHub](https://github.com/fl-sean03/iff-parameters) | "
    "[UPM](https://github.com/fl-sean03/upm) | "
    "[Docs](https://github.com/fl-sean03/iff-parameters/tree/main/docs)"
)

# --- Home Page ---
st.title("INTERFACE Force Field Parameters Browser")
st.caption("Central library • Heinz Lab • University of Colorado Boulder")

stats = get_library_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Parameter Sets", stats["n_parameter_entries"])
c2.metric("Structures", stats["n_structure_entries"])
c3.metric("Atom Types (param)", stats["total_atom_types"])
c4.metric("Materials Covered", stats["n_materials"])

st.markdown("---")

# Two columns: parameter sets (left) + recent structures summary (right)
tabs = st.tabs(["Parameter Sets", "Structure Database", "Quick Links"])

with tabs[0]:
    st.subheader("Parameter Sets")
    param_entries = list_parameter_entries()
    if not param_entries:
        st.warning(
            "No parameter sets found. If you just cloned the repo, run:\n\n"
            "```\npython scripts/seed_from_interface_ff15_parameters.py\n```"
        )
    for entry in param_entries:
        label = f"**{entry['name']}** @ {entry['version']} ({entry['format'].upper()})"
        if entry.get("partial_roundtrip"):
            label += "  ⚠ partial roundtrip"
        if entry.get("deprecated"):
            label += "  🚫 deprecated"
        with st.expander(label):
            cols = st.columns([2, 3])
            with cols[0]:
                st.write(f"**Author:** {entry.get('author', 'Unknown')}")
                st.write(f"**Format:** {entry['format'].upper()}")
                if entry.get("doi"):
                    st.write(f"**DOI:** [{entry['doi']}](https://doi.org/{entry['doi']})")
                if entry.get("supersedes"):
                    st.write(f"**Supersedes:** {entry['supersedes']}")
            with cols[1]:
                mats = entry.get("materials", [])
                st.write(f"**Materials:** {', '.join(mats) if mats else 'Not specified'}")
                st.caption(f"Path: `{entry['path']}`")

with tabs[1]:
    st.subheader("Structure Database")
    structures = list_structure_entries()
    if not structures:
        st.warning(
            "No structures found. Run:\n\n"
            "```\npython scripts/seed_from_interface_ff15_structures.py\n```"
        )
    else:
        by_class: dict[str, int] = {}
        by_family: dict[str, int] = {}
        for s in structures:
            by_class[s["material_class"]] = by_class.get(s["material_class"], 0) + 1
            family = s.get("atom_type_family") or "(unknown)"
            by_family[family] = by_family.get(family, 0) + 1

        st.write(f"**{len(structures)} structures** totalling "
                 f"**{stats['n_structure_atoms_total']:,} atoms** across "
                 f"**{len(by_class)} material classes**.")

        c1, c2 = st.columns(2)
        with c1:
            st.write("**By material class:**")
            for k, v in sorted(by_class.items()):
                st.write(f"- {k}: {v}")
        with c2:
            st.write("**By parameter family:**")
            for k, v in sorted(by_family.items()):
                st.write(f"- {k}: {v}")

        st.caption("Go to **Browse** to drill into specific structures.")

with tabs[2]:
    st.markdown("""
    ### Quick links
    - **Browse** — explore parameter sets and structures side-by-side
    - **Search** — find entries by atom type or material
    - **Compare** — diff two parameter versions
    - **Download** — pull parameters + structures (latest, original, or specific version)
    - **Upload** — ingest a new parameter file
    - **Upload Structure** — ingest a pre-parameterized structure
    - **Conflicts** — cross-entry key collisions with value disagreements
    - **Coverage** — materials × families matrix
    """)

st.markdown("---")
st.caption("Powered by UPM v2.1 • Library schema v0.2")
