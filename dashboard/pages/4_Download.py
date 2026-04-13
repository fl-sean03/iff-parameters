"""Download: parameters + structures, with pull_latest / original / specific."""
from __future__ import annotations

import io
import json
import zipfile

import streamlit as st

from utils.data import (
    list_parameter_entries, list_structure_entries,
    load_bundle_tables, load_structure_atoms, load_structure_geometry_text,
    load_manifest,
)
from utils.export import export_as_frc, export_as_prm, export_tables_csv_zip

st.title("Download")

tabs = st.tabs(["Parameters", "Structure + Parameters"])

# ============================== Parameters ================================
with tabs[0]:
    bundles = list_parameter_entries()
    if not bundles:
        st.info("No parameter entries.")
        st.stop()

    labels = [f"{e['ref']} ({e['format']})" for e in bundles]
    idx = st.selectbox("Entry:", range(len(labels)),
                       format_func=lambda i: labels[i], key="dl_param_sel")
    entry = bundles[idx]
    tables = load_bundle_tables(entry["path"])

    st.markdown("---")
    fmt = entry["format"]
    format_options = ["CSV (ZIP)"]
    if fmt == "cvff":
        format_options.insert(0, "CVFF (.frc)")
    elif fmt == "charmm":
        format_options.insert(0, "CHARMM (.prm)")
    selected_format = st.radio("Export format:", format_options, key="dl_fmt")

    st.subheader("Tables to include")
    selected_tables = {}
    table_names = sorted(tables.keys())
    cols = st.columns(3)
    for i, name in enumerate(table_names):
        with cols[i % 3]:
            if st.checkbox(f"{name} ({len(tables[name])} rows)", value=True, key=f"dl_sel_{name}"):
                selected_tables[name] = tables[name]

    if not selected_tables:
        st.warning("Select at least one table.")
        st.stop()

    with st.expander("Preview (first 5 rows per table)"):
        for name, df in sorted(selected_tables.items()):
            st.caption(f"**{name}**")
            st.dataframe(df.head(5), use_container_width=True)

    base = f"{entry['name']}_{entry['version']}"
    if selected_format == "CSV (ZIP)":
        st.download_button("Download CSV ZIP",
                           export_tables_csv_zip(selected_tables),
                           f"{base}.zip", "application/zip")
    elif selected_format == "CVFF (.frc)":
        st.download_button("Download .frc",
                           export_as_frc(selected_tables),
                           f"{base}.frc", "application/octet-stream")
    elif selected_format == "CHARMM (.prm)":
        st.download_button("Download .prm",
                           export_as_prm(selected_tables),
                           f"{base}.prm", "application/octet-stream")

# ====================== Structure + Parameters (pull) =====================
with tabs[1]:
    structs = list_structure_entries()
    if not structs:
        st.info("No structures.")
        st.stop()

    classes = sorted({s["material_class"] for s in structs})
    sel_class = st.selectbox("Material class:", classes, key="dl_struct_class")
    in_class = [s for s in structs if s["material_class"] == sel_class]
    labels = [f"{s['name']}@{s['version']} ({s['n_atoms']} atoms)" for s in in_class]
    idx = st.selectbox("Structure:", range(len(labels)),
                       format_func=lambda i: labels[i], key="dl_struct_sel")
    s = in_class[idx]

    st.write("**Pinned:** " + ", ".join(f"`{p['name']}@{p['version']}`"
                                          for p in s.get("parameterized_with", [])))
    if s.get("lock_to_original"):
        st.warning("Structure is locked to original. `pull_latest` will return the original.")

    st.markdown("**How do you want the parameters resolved?**")
    mode = st.radio(
        "Pull mode:",
        ["latest (recommended)", "original (exact pin)", "specific version"],
        key="dl_mode",
    )

    # Run the pull
    from iff_parameters.entries import list_structure_entries as list_structure_entries_backend
    # Re-find the matching Entry by path
    backend_entries = list_structure_entries_backend()
    structure_entry = next((e for e in backend_entries if str(e.path) == s["path"]), None)
    if structure_entry is None:
        st.error("Could not reopen structure via backend — path mismatch.")
        st.stop()

    from iff_parameters.pull import pull_latest, pull_original, pull_version

    if mode.startswith("latest"):
        result = pull_latest(structure_entry)
    elif mode.startswith("original"):
        result = pull_original(structure_entry)
    else:
        # specific version per family
        specific = {}
        for p_ref in s.get("parameterized_with", []):
            fam = p_ref["name"]
            # find available versions
            avail = sorted({
                e["version"] for e in list_parameter_entries() if e["name"] == fam
            })
            if not avail:
                continue
            v = st.selectbox(f"{fam}:", avail, key=f"dl_specific_{fam}")
            specific[fam] = v
        # just pick the first family (single-family structures dominate here);
        # for multi-family use pull_version per family and merge
        if specific:
            first_fam, first_ver = next(iter(specific.items()))
            result = pull_version(structure_entry, first_fam, first_ver)
        else:
            st.error("No available versions to choose from.")
            st.stop()

    # Display status + banners
    status_label = {"OK": "✅ OK", "WARNING": "⚠️ WARNING", "ERROR": "❌ ERROR"}.get(result.status, result.status)
    st.subheader(f"Status: {status_label}")
    for m in result.messages:
        st.info(m)

    # Per-family resolution details
    with st.expander("Resolution detail"):
        for fam, res in result.resolutions.items():
            st.write(f"**{fam}**: requested `{res['requested']}`, resolved `{res.get('resolved')}`")
            if res.get("renames_applied"):
                st.caption("Renames: " + ", ".join(f"{a}→{b}" for a, b in res["renames_applied"].items()))
            if res.get("breaking_crossed"):
                st.caption("Breaking change crossed in lineage")
            if res.get("missing"):
                st.caption("Missing: " + json.dumps(res["missing"]))

    # Offer a bundled download if there's anything to download
    if result.parameters:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Structure side
            atoms = load_structure_atoms(s["path"])
            zf.writestr(f"{s['name']}/{s['version']}/atoms.csv", atoms.to_csv(index=False))
            geom = load_structure_geometry_text(s["path"])
            zf.writestr(f"{s['name']}/{s['version']}/geometry/source.car", geom)
            zf.writestr(
                f"{s['name']}/{s['version']}/manifest.json",
                json.dumps(load_manifest(s["path"]), indent=2, sort_keys=True) + "\n",
            )

            # Parameter side — one subtree per family
            for fam, bundle in result.parameters.items():
                resolved_version = result.resolutions[fam]["resolved"]
                prefix = f"parameters/{fam}/{resolved_version}"
                zf.writestr(f"{prefix}/manifest.json",
                            json.dumps(bundle.manifest, indent=2, sort_keys=True) + "\n")
                for tname, df in bundle.tables.items():
                    zf.writestr(f"{prefix}/tables/{tname}.csv", df.to_csv(index=False))
                zf.writestr(f"{prefix}/raw/source.frc", bundle.raw.get("source_text", ""))

            # Resolution report
            zf.writestr(
                "pull_report.json",
                json.dumps({
                    "mode": mode,
                    "structure": s["ref"],
                    "status": result.status,
                    "messages": result.messages,
                    "resolutions": result.resolutions,
                }, indent=2, sort_keys=True, default=str) + "\n",
            )
        buf.seek(0)

        st.download_button(
            f"Download structure + parameters ({mode.split(' ', 1)[0]})",
            buf,
            f"{s['name']}_{s['version']}_{mode.split(' ', 1)[0]}.zip",
            "application/zip",
        )
    else:
        st.error("No parameters resolved — nothing to download.")
