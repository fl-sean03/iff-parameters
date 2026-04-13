"""Upload a new parameter file with conflict preview + intent declaration."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data import (
    get_data_dir, list_parameter_entries, load_bundle_tables,
)

st.title("Upload Parameters")
st.caption("Drag and drop .frc or .prm files. Conflicts are previewed before ingest.")

uploaded_files = st.file_uploader(
    "Upload force field files",
    type=["frc", "prm"],
    accept_multiple_files=True,
    help="Supports CVFF .frc (LAMMPS) and CHARMM .prm (NAMD).",
)

if not uploaded_files:
    st.info("Upload one or more .frc / .prm files to get started.")
    st.stop()


def _parse(content: str, fmt: str):
    if fmt == "frc":
        from upm.codecs.msi_frc import parse_frc_text
        return parse_frc_text(content, validate=False)
    from upm.codecs._charmm_parser import parse_prm_text
    from upm.core.tables import normalize_tables
    tables, raw = parse_prm_text(content)
    return normalize_tables(tables), raw


def _detect_collisions(new_tables: dict, existing_entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (atom_type_collisions, bond_collisions).

    Each row: entry_ref, key, your_values, their_values, disagreement_cols.
    """
    import math
    atom_rows, bond_rows = [], []
    new_at = new_tables.get("atom_types")
    new_bonds = new_tables.get("bonds")
    for entry in existing_entries:
        try:
            ex = load_bundle_tables(entry["path"])
        except Exception:
            continue
        # atom types
        if new_at is not None and "atom_types" in ex:
            ex_at = ex["atom_types"]
            common = set(new_at["atom_type"].astype(str)) & set(ex_at["atom_type"].astype(str))
            for t in sorted(common):
                new_row = new_at[new_at["atom_type"] == t].iloc[0].to_dict()
                old_row = ex_at[ex_at["atom_type"] == t].iloc[0].to_dict()
                disagreements = []
                for col in ("lj_a", "lj_b", "mass_amu"):
                    nv, ov = new_row.get(col), old_row.get(col)
                    try:
                        if nv is None or ov is None:
                            continue
                        fnv, fov = float(nv), float(ov)
                        if math.isnan(fnv) and math.isnan(fov):
                            continue
                        if abs(fnv - fov) > 1e-6 * max(abs(fnv), abs(fov), 1.0):
                            disagreements.append(col)
                    except (TypeError, ValueError):
                        if str(nv) != str(ov):
                            disagreements.append(col)
                atom_rows.append({
                    "entry": entry["ref"],
                    "atom_type": t,
                    "disagrees_on": ", ".join(disagreements) if disagreements else "—",
                    "status": "⚠ conflict" if disagreements else "✓ duplicate",
                })
        # bonds
        if new_bonds is not None and "bonds" in ex:
            ex_bonds = ex["bonds"]
            new_keys = set(zip(new_bonds["t1"].astype(str), new_bonds["t2"].astype(str)))
            ex_keys = set(zip(ex_bonds["t1"].astype(str), ex_bonds["t2"].astype(str)))
            common_bonds = new_keys & ex_keys
            for k in sorted(common_bonds):
                new_row = new_bonds[(new_bonds["t1"] == k[0]) & (new_bonds["t2"] == k[1])].iloc[0].to_dict()
                old_row = ex_bonds[(ex_bonds["t1"] == k[0]) & (ex_bonds["t2"] == k[1])].iloc[0].to_dict()
                disagreements = []
                for col in ("k", "r0"):
                    nv, ov = new_row.get(col), old_row.get(col)
                    try:
                        fnv, fov = float(nv), float(ov)
                        if math.isnan(fnv) and math.isnan(fov):
                            continue
                        if abs(fnv - fov) > 1e-6 * max(abs(fnv), abs(fov), 1.0):
                            disagreements.append(col)
                    except (TypeError, ValueError):
                        if str(nv) != str(ov):
                            disagreements.append(col)
                bond_rows.append({
                    "entry": entry["ref"],
                    "bond": f"{k[0]} — {k[1]}",
                    "disagrees_on": ", ".join(disagreements) if disagreements else "—",
                    "status": "⚠ conflict" if disagreements else "✓ duplicate",
                })
    return atom_rows, bond_rows


for uploaded in uploaded_files:
    with st.expander(f"**{uploaded.name}** ({uploaded.size / 1024:.0f} KB)", expanded=True):
        content = uploaded.read().decode("utf-8", errors="replace")
        uploaded.seek(0)
        fmt = "frc" if uploaded.name.endswith(".frc") else "prm"

        try:
            tables, raw = _parse(content, fmt)
        except Exception as e:
            st.error(f"Parse failed: {e}")
            continue

        c = st.columns(4)
        c[0].metric("Format", fmt.upper())
        c[1].metric("Atom types", len(tables.get("atom_types", [])))
        c[2].metric("Bonds", len(tables.get("bonds", [])))
        c[3].metric("Angles", len(tables.get("angles", [])))

        # --- Conflict preview ---
        st.markdown("---")
        st.subheader("Conflict preview")
        existing = list_parameter_entries()
        atom_rows, bond_rows = _detect_collisions(tables, existing)

        with st.expander(f"Atom-type collisions ({len(atom_rows)})"):
            if atom_rows:
                st.dataframe(pd.DataFrame(atom_rows), use_container_width=True, hide_index=True)
            else:
                st.write("None.")
        with st.expander(f"Bond collisions ({len(bond_rows)})"):
            if bond_rows:
                st.dataframe(pd.DataFrame(bond_rows), use_container_width=True, hide_index=True)
            else:
                st.write("None.")

        n_conflicts = sum(1 for r in atom_rows if "conflict" in r["status"]) \
                      + sum(1 for r in bond_rows if "conflict" in r["status"])
        n_dupes = len(atom_rows) + len(bond_rows) - n_conflicts
        if n_conflicts:
            st.warning(f"{n_conflicts} real disagreement(s) detected. Declare intent below.")
        else:
            st.success(f"No disagreements. {n_dupes} harmless duplicate(s).")

        # --- Intent declaration ---
        st.markdown("---")
        st.subheader("Intent")
        intent = st.radio(
            "How should this ingest be treated?",
            options=[
                "new family (never seen before)",
                "new version of an existing family",
                "intentional override (extends a base FF)",
                "fork of an existing family (diverged on purpose)",
            ],
            key=f"intent_{uploaded.name}",
        )

        icols = st.columns(2)
        with icols[0]:
            if intent.startswith("new version"):
                existing_names = sorted({e["name"] for e in existing})
                family_name = st.selectbox("Family:", existing_names, key=f"fam_{uploaded.name}")
                version = st.text_input("Version", value="v1.1", key=f"ver_{uploaded.name}")
                supersedes = st.text_input("Supersedes (previous version)", value="v1.0",
                                           key=f"sup_{uploaded.name}")
                parent_ff = None
                overrides_input = ""
            elif intent.startswith("intentional override"):
                family_name = st.text_input("New family name", key=f"fam_{uploaded.name}",
                                             value=Path(uploaded.name).stem)
                version = st.text_input("Version", value="v1.0", key=f"ver_{uploaded.name}")
                all_refs = [e["ref"] for e in existing]
                parent_ref = st.selectbox("Parent FF (base to extend):",
                                          all_refs, key=f"parent_{uploaded.name}")
                parent_ff = parent_ref.replace("@", "/")
                supersedes = None
                overrides_input = st.text_input(
                    "Scopes this explicitly overrides (comma-separated):",
                    value="atom_types, bonds",
                    key=f"ov_{uploaded.name}",
                )
            else:
                family_name = st.text_input("Family name", value=Path(uploaded.name).stem,
                                             key=f"fam_{uploaded.name}")
                version = st.text_input("Version", value="v1.0", key=f"ver_{uploaded.name}")
                parent_ff = None
                supersedes = None
                overrides_input = ""
        with icols[1]:
            author = st.text_input("Author", value="", key=f"auth_{uploaded.name}")
            materials = st.text_input("Materials (comma-separated)", key=f"mat_{uploaded.name}")
            notes = st.text_area("Notes", key=f"notes_{uploaded.name}")

        ack = st.checkbox(
            "I've reviewed the conflict report above.",
            value=(n_conflicts == 0),
            key=f"ack_{uploaded.name}",
        )

        if st.button(f"Ingest {uploaded.name}", key=f"btn_{uploaded.name}",
                     type="primary", disabled=not ack):
            try:
                from upm.bundle.io import save_package
                data_dir = Path(get_data_dir()) / "parameters"
                root = data_dir / family_name / version
                if root.exists():
                    st.error(f"{root.relative_to(data_dir.parent.parent.parent.parent)} already exists. "
                             f"Bump the version.")
                    continue

                nonbonded = ({"style": "A-B", "form": "12-6", "mixing": "geometric"} if fmt == "frc"
                             else {"style": "eps-rmin", "form": "12-6", "mixing": "arithmetic"})
                file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                provenance = {
                    "author": author or "unknown",
                    "lab": "Heinz Lab, CU Boulder",
                    "date_created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "source_file": uploaded.name,
                    "source_sha256": file_hash,
                    "materials": [m.strip() for m in materials.split(",") if m.strip()],
                    "notes": notes,
                    "intent": intent,
                    "ingested_utc": datetime.now(timezone.utc)
                        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                }

                overrides = None
                if overrides_input:
                    scopes = [s.strip() for s in overrides_input.split(",") if s.strip()]
                    overrides = [{"target": parent_ff, "scope": s, "reason": notes or "user-declared"}
                                 for s in scopes]

                save_package(
                    root,
                    name=family_name, version=version,
                    tables=tables,
                    source_text=content, source_format=fmt,
                    unknown_sections=raw, nonbonded=nonbonded,
                    provenance=provenance,
                    supersedes=supersedes,
                    parent_ff=parent_ff,
                    overrides=overrides,
                )
                st.success(f"Ingested **{family_name}@{version}** "
                           f"({len(tables.get('atom_types', []))} atom types)")
                st.cache_data.clear()
                st.balloons()
            except Exception as e:
                st.error(f"Ingest failed: {e}")
