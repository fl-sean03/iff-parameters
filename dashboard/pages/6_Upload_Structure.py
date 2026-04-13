"""Upload a pre-parameterized structure (.car / .mdf / .pdb)."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from iff_parameters.car_parser import load_car_atoms, parse_car_atoms_tolerant
from utils.data import (
    get_data_dir, list_parameter_entries, load_bundle_tables,
)

st.title("Upload Structure")
st.caption("Ingest a pre-parameterized structure that pins to one or more parameter entries.")


def _parse_structure(content: str, filename: str) -> tuple[pd.DataFrame, str]:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "car":
        # Write to a temp file so USM can try its parser; fall back to tolerant.
        with tempfile.NamedTemporaryFile("w", suffix=".car", delete=False) as fh:
            fh.write(content)
            tmp_path = Path(fh.name)
        try:
            return load_car_atoms(tmp_path), "car"
        except Exception:
            return parse_car_atoms_tolerant(content), "car"
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass
    if ext == "pdb":
        st.error("PDB ingestion not yet supported in the dashboard. Upload a .car instead.")
        return pd.DataFrame(), "pdb"
    if ext == "mdf":
        st.error("MDF alone is not enough — upload a .car (and optional companion .mdf).")
        return pd.DataFrame(), "mdf"
    st.error(f"Unsupported extension: {ext}")
    return pd.DataFrame(), ext


# --- UI --------------------------------------------------------------------

uploaded = st.file_uploader(
    "Drop a structure file",
    type=["car", "mdf", "pdb"],
    accept_multiple_files=False,
    help="Currently supports .car (Materials Studio). PDB support is limited.",
)

if not uploaded:
    st.info("Upload a .car file (or .pdb). Atoms table with ff_type + charge is required.")
    st.stop()

content = uploaded.read().decode("utf-8", errors="replace")
atoms_df, fmt = _parse_structure(content, uploaded.name)

if atoms_df.empty:
    st.error("Could not parse any atoms. Check that the file contains ff_type column.")
    st.stop()

st.success(f"Parsed {len(atoms_df)} atoms from {uploaded.name}")

c1, c2, c3 = st.columns(3)
c1.metric("Atoms", len(atoms_df))
unique_types = sorted(set(atoms_df["ff_type"].astype(str)))
c2.metric("Unique atom types", len(unique_types))
total_charge = float(atoms_df["charge"].sum())
c3.metric("Total charge", f"{total_charge:+.3f}")

with st.expander("Atom types used"):
    st.write(", ".join(f"`{t}`" for t in unique_types))

st.dataframe(atoms_df.head(50), use_container_width=True)
if len(atoms_df) > 50:
    st.caption(f"Showing first 50 of {len(atoms_df)} atoms.")

st.markdown("---")

# --- Family detection (which parameter entries cover these types?) ----------

st.subheader("Detect parameter family")
param_entries = list_parameter_entries()
coverage_report = []
for p in param_entries:
    tables = load_bundle_tables(p["path"])
    at = tables.get("atom_types")
    if at is None or len(at) == 0:
        continue
    fam_types = set(at["atom_type"].astype(str))
    missing = sorted(set(unique_types) - fam_types)
    coverage_report.append({
        "Entry": p["ref"],
        "Covers all": "✅" if not missing else "❌",
        "Missing types": ", ".join(missing[:4]) + ("…" if len(missing) > 4 else ""),
        "Missing count": len(missing),
    })
coverage_df = pd.DataFrame(coverage_report).sort_values("Missing count", ascending=True)
st.dataframe(coverage_df, use_container_width=True, hide_index=True)

# Auto-suggest the first family with zero missing
candidates = coverage_df[coverage_df["Missing count"] == 0]["Entry"].tolist()
default_family = candidates[0] if candidates else (param_entries[0]["ref"] if param_entries else "")

# --- Metadata inputs -------------------------------------------------------

st.markdown("---")
st.subheader("Metadata")

c1, c2 = st.columns(2)
with c1:
    material_class = st.text_input(
        "Material class (sub-directory under structures/)",
        value="uncategorized",
        help="e.g. silica, mxene, clay, metals",
    )
    model_name = st.text_input(
        "Model name",
        value=Path(uploaded.name).stem,
        help="Directory name for this structure (no spaces, no +)",
    )
    version = st.text_input("Version", value="v1.0")
with c2:
    all_refs = [p["ref"] for p in param_entries]
    param_refs = st.multiselect(
        "Parameterized with (one or more)",
        options=all_refs,
        default=[default_family] if default_family in all_refs else [],
        help="The exact parameter version(s) this structure was parameterized against.",
    )
    primary_family_ref = st.selectbox(
        "Primary atom_type_family",
        options=param_refs if param_refs else ["(select parameter first)"],
        help="The family whose atom-type names appear in the atoms above.",
    )
    lock_to_original = st.checkbox("Lock to original (pull_latest disabled)")

author = st.text_input("Author", value="")
notes = st.text_area("Notes", placeholder="(optional)")

# --- Ingest ----------------------------------------------------------------

st.markdown("---")
ingest_clicked = st.button("Ingest structure", type="primary", disabled=not param_refs)

if ingest_clicked:
    if primary_family_ref.startswith("("):
        st.error("Select a primary atom_type_family.")
        st.stop()

    slug_model = model_name.strip().replace(" ", "_").replace("+", "-").replace(".", "_")
    target_root = Path(get_data_dir()) / "structures" / material_class / slug_model / version
    if target_root.exists():
        st.error(f"Already exists at {target_root.relative_to(Path(get_data_dir()).parent.parent.parent)}. "
                 f"Bump the version number.")
        st.stop()

    # Convert ref strings "name@version" → dicts
    pw = []
    for r in param_refs:
        name, v = r.split("@")
        pw.append({"name": name, "version": v})
    family_name = primary_family_ref.split("@", 1)[0]

    provenance = {
        "author": author or "unknown",
        "lab": "Heinz Lab, CU Boulder",
        "source_file": uploaded.name,
        "materials": [material_class],
        "notes": notes,
        "ingested_utc": datetime.now(timezone.utc)
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }

    from upm.bundle.io import save_structure
    try:
        save_structure(
            target_root,
            name=slug_model, version=version,
            atoms_df=atoms_df, geometry_text=content, geometry_format=fmt,
            atom_type_family=family_name,
            parameterized_with=pw,
            lock_to_original=lock_to_original,
            provenance=provenance,
        )
        st.success(f"Ingested `{material_class}/{slug_model}@{version}` → {family_name}")
        st.balloons()
        st.cache_data.clear()
        st.code(f"Committed at {target_root}")
    except Exception as e:
        st.error(f"Ingest failed: {e}")
