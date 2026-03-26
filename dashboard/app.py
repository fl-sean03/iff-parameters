"""IFF Parameters Browser — Heinz Lab Force Field Dashboard."""
import streamlit as st

st.set_page_config(
    page_title="IFF Parameters Browser",
    page_icon="https://raw.githubusercontent.com/hendrikheinz/INTERFACE-force-field-and-surface-models/master/README.md",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.data import list_bundles, get_bundle_stats

# --- Sidebar ---
st.sidebar.title("IFF Parameters")
st.sidebar.caption("Heinz Lab, CU Boulder")
st.sidebar.markdown("---")
st.sidebar.info(
    "Browse, search, compare, and download\n"
    "INTERFACE Force Field parameters.\n\n"
    "[GitHub](https://github.com/fl-sean03/iff-parameters) | "
    "[UPM](https://github.com/fl-sean03/upm)"
)

# --- Home Page ---
st.title("INTERFACE Force Field Parameters Browser")
st.caption("Curated parameter bundles from the Heinz Lab | University of Colorado Boulder")

# Metrics
stats = get_bundle_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Bundles", stats["n_bundles"])
c2.metric("Atom Types", stats["total_atoms"])
c3.metric("Bonded Params", stats["total_bonds"] + stats["total_angles"])
c4.metric("Torsions + OOP", stats["total_torsions"] + stats["total_oop"])

st.markdown("---")

# Bundle overview
st.subheader("Available Parameter Sets")
bundles = list_bundles()
for entry in bundles:
    with st.expander(f"**{entry['name']}** @ {entry['version']} ({entry['format'].upper()})"):
        cols = st.columns([2, 3])
        with cols[0]:
            st.write(f"**Author:** {entry.get('author', 'Unknown')}")
            st.write(f"**Format:** {entry['format'].upper()}")
            if entry.get("doi"):
                st.write(f"**DOI:** [{entry['doi']}](https://doi.org/{entry['doi']})")
        with cols[1]:
            materials = entry.get("materials", [])
            st.write(f"**Materials:** {', '.join(materials) if materials else 'Not specified'}")

st.markdown("---")

# Materials coverage
st.subheader("Materials Coverage")
all_materials = stats["materials"]
if all_materials:
    cols = st.columns(min(len(all_materials), 6))
    for i, mat in enumerate(all_materials):
        cols[i % 6].button(mat, key=f"mat_{mat}", use_container_width=True)

st.markdown("---")
st.caption("Powered by UPM v2.0 | Data: iff-parameters v0.1.0")

# Debug: show data path resolution (remove after deployment is verified)
from utils.data import get_data_dir as _gdd
from pathlib import Path as _P
with st.expander("Debug: path resolution"):
    dd = _gdd()
    st.code(f"Data dir: {dd}\nExists: {_P(dd).is_dir()}\nContents: {list(_P(dd).iterdir()) if _P(dd).is_dir() else 'N/A'}")
