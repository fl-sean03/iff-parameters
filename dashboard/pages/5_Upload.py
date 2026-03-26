"""Upload and ingest new force field files."""
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data import list_bundles, load_bundle_tables, get_data_dir

st.title("Upload Parameters")
st.caption("Drag and drop .frc or .prm files to ingest into the repository.")

uploaded_files = st.file_uploader(
    "Upload force field files",
    type=["frc", "prm"],
    accept_multiple_files=True,
    help="Supports CVFF .frc (LAMMPS) and CHARMM .prm (NAMD) files",
)

if not uploaded_files:
    st.info("Upload one or more .frc / .prm files to get started.")
    st.stop()

# Process each uploaded file
for uploaded in uploaded_files:
    with st.expander(f"**{uploaded.name}** ({uploaded.size / 1024:.0f} KB)", expanded=True):
        content = uploaded.read().decode("utf-8")
        uploaded.seek(0)

        # Detect format
        fmt = "frc" if uploaded.name.endswith(".frc") else "prm"

        # Parse
        try:
            if fmt == "frc":
                from upm.codecs.msi_frc import parse_frc_text
                tables, raw = parse_frc_text(content, validate=False)
            else:
                from upm.codecs._charmm_parser import parse_prm_text
                from upm.core.tables import normalize_tables
                tables, raw = parse_prm_text(content)
                tables = normalize_tables(tables)

            # Show summary
            cols = st.columns(4)
            cols[0].metric("Format", fmt.upper())
            cols[1].metric("Atom Types", len(tables.get("atom_types", [])))
            cols[2].metric("Bonds", len(tables.get("bonds", [])))
            cols[3].metric("Angles", len(tables.get("angles", [])))

            # Show atom types preview
            if "atom_types" in tables and len(tables["atom_types"]) > 0:
                with st.container():
                    st.caption("Atom types (first 20)")
                    preview = tables["atom_types"].head(20)
                    display_cols = [c for c in ["atom_type", "element", "mass_amu", "lj_a", "lj_b"]
                                   if c in preview.columns]
                    st.dataframe(preview[display_cols], use_container_width=True, height=200)

            # Similarity check against existing bundles
            st.markdown("**Similarity to existing bundles:**")
            existing = list_bundles()
            if not existing:
                st.write("No existing bundles to compare against.")
            elif "atom_types" not in tables or len(tables["atom_types"]) == 0:
                st.write("No atom types found — cannot compare.")
            else:
                new_types = set(tables["atom_types"]["atom_type"].tolist())
                similarities = []
                for entry in existing:
                    try:
                        ex_tables = load_bundle_tables(entry["path"])
                        if "atom_types" not in ex_tables:
                            continue
                        ex_types = set(ex_tables["atom_types"]["atom_type"].tolist())
                        common = new_types & ex_types
                        union = new_types | ex_types
                        overlap = len(common) / len(union) * 100 if union else 0
                        if overlap > 30:
                            similarities.append({
                                "Bundle": f"{entry['name']}@{entry['version']}",
                                "Overlap": f"{overlap:.0f}%",
                                "Common": len(common),
                                "New Only": len(new_types - ex_types),
                                "Existing Only": len(ex_types - new_types),
                            })
                    except Exception:
                        continue

                if similarities:
                    sim_df = pd.DataFrame(similarities).sort_values("Overlap", ascending=False)
                    st.dataframe(sim_df, use_container_width=True, hide_index=True)

                    best = similarities[0]
                    if float(best["Overlap"].rstrip("%")) > 90:
                        st.warning(
                            f"This file is {best['Overlap']} similar to **{best['Bundle']}**. "
                            f"Consider ingesting as a new version of that bundle instead of a new bundle."
                        )
                else:
                    st.success("No significant overlap with existing bundles — this appears to be a new parameter set.")

            # Ingest controls
            st.markdown("---")
            st.markdown("**Ingest settings:**")
            icols = st.columns(2)
            with icols[0]:
                suggested_name = uploaded.name.replace("_", "-").replace("+", "-").lower()
                suggested_name = Path(suggested_name).stem
                bundle_name = st.text_input("Bundle name", value=suggested_name, key=f"name_{uploaded.name}")
                version = st.text_input("Version", value="v1.0", key=f"ver_{uploaded.name}")
            with icols[1]:
                author = st.text_input("Author", value="Hendrik Heinz", key=f"auth_{uploaded.name}")
                materials = st.text_input("Materials (comma-separated)", key=f"mat_{uploaded.name}")
                notes = st.text_input("Notes", key=f"notes_{uploaded.name}")

            if st.button(f"Ingest {uploaded.name}", key=f"btn_{uploaded.name}", type="primary"):
                try:
                    from upm.bundle.io import save_package
                    import hashlib

                    data_dir = Path(get_data_dir())
                    root = data_dir / bundle_name / version

                    units = {"length": "angstrom", "energy": "kcal/mol", "mass": "amu", "angle": "degree"}
                    nonbonded = ({"style": "A-B", "form": "12-6", "mixing": "geometric"} if fmt == "frc"
                                 else {"style": "eps-rmin", "form": "12-6", "mixing": "arithmetic"})

                    save_package(root, name=bundle_name, version=version, tables=tables,
                                 source_text=content, unknown_sections=raw,
                                 units=units, nonbonded=nonbonded)

                    # Patch provenance
                    file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    from datetime import datetime, timezone
                    manifest_path = root / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["provenance"] = {
                        "author": author,
                        "lab": "Heinz Lab, CU Boulder",
                        "date_created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "source_file": uploaded.name,
                        "source_sha256": file_hash,
                        "materials": [m.strip() for m in materials.split(",") if m.strip()],
                        "notes": notes,
                        "ingested_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    }
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

                    st.success(f"Ingested **{bundle_name}@{version}** — {len(tables.get('atom_types', []))} atom types")
                    st.cache_data.clear()
                    st.balloons()

                except Exception as e:
                    st.error(f"Ingest failed: {e}")

        except Exception as e:
            st.error(f"Failed to parse {uploaded.name}: {e}")
