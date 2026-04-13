# IFF Parameters — Architecture Specification

**Version:** 0.2.0-draft
**Status:** Proposed (pending approval)
**Supersedes:** v0.1.0 ad-hoc schema

This is the authoritative specification for the IFF Parameters central library. Any question about what the system does (or should do) should be answerable here. Changes to this spec require an architectural review.

---

## 1. Purpose

A single central, git-versioned library that holds:
- Force field parameter sets (`.frc`, `.prm`)
- Pre-parameterized molecular structures pinned to specific parameter versions
- Metadata enabling cross-version queries, conflict detection, and reproducibility

Seeded from the Hendrik Heinz INTERFACE Force Field v1.5 distribution. Grows over time via upload from group members.

## 2. Non-goals

- Not a parameterization engine (no structure→types inference — see BACKLOG).
- Not a simulation runner. Consumers (LAMMPS, NAMD, GROMACS) are downstream.
- Not a real-time multi-user write backend. Writes go through git.
- No version DAGs, branching, or semver constraint solving. Versions are linear per family.

## 3. Data model

### 3.1 Entry types

Every item in the library is one of two Entry kinds:

- **Parameter Entry** — a snapshot of a force field (atom types, bonds, angles, torsions, OOP, equivalences). Derived from a `.frc`/`.prm` source.
- **Structure Entry** — a pre-parameterized molecular geometry (atom positions, elements, per-atom FF types, per-atom charges). Pinned to one or more Parameter Entries at upload.

Both are immutable after publish.

### 3.2 Directory layout

```
src/iff_parameters/data/
  parameters/
    <family>/<version>/
      manifest.json
      tables/{atom_types, bonds, angles, torsions, out_of_plane, equivalences}.csv
      raw/source.frc   (or source.prm)
      raw/unknown_sections.json
  structures/
    <material_class>/<model_name>/<version>/
      manifest.json
      geometry/source.car   (+ .mdf, or .pdb, etc.)
      atoms.csv             (per-atom: id, element, ff_type, charge, x, y, z)
      topology.csv          (bonds/angles/dihedrals referenced)
  archive/
    <old_bundles>/          (deprecated entries, excluded from discovery)
```

All directories under `parameters/` and `structures/` are immutable once committed to main.

### 3.3 Versioning

Format: `v<major>.<minor>` (e.g., `v1.0`, `v1.1`, `v2.0`).
- **Minor bump**: refinement, bug fix, backward-compatible addition.
- **Major bump**: breaking change (rename, removal, units/style change) — must declare `breaking: true`.

Version strings are unique within a family. CI blocks duplicates.

## 4. Manifest schema

Every entry has a `manifest.json` at its root.

### 4.1 Common fields

```json
{
  "schema_version": "0.2.0",
  "name": "cvff-mxene-additions",
  "version": "v1.1",
  "type": "parameters" | "structure",
  "created_utc": "2026-04-13T12:00:00Z",
  "supersedes": "v1.0",                   // optional
  "deprecated": false,
  "deprecation_reason": null,
  "provenance": {
    "author": "Alice Smith",
    "lab": "Heinz Lab, CU Boulder",
    "source_file": "cvff_mxene_v1_1.frc",
    "source_sha256": "...",
    "notes": "Refined Ti-O bond after DFT benchmark",
    "materials": ["MXene", "Ti3C2"],
    "publication_doi": "10.1021/...",
    "date_created": "2026-04-10"
  }
}
```

### 4.2 Parameter Entry additional fields

```json
{
  "units": {"length": "angstrom", "energy": "kcal/mol", "mass": "amu", "angle": "degree"},
  "nonbonded": {"style": "A-B", "form": "12-6", "mixing": "geometric"},
  "tables": {
    "atom_types": {"path": "tables/atom_types.csv", "rows": 42, "sha256": "..."},
    "bonds":      {"path": "tables/bonds.csv",       "rows": 80, "sha256": "..."}
    // ...
  },
  "parent_ff": "cvff-interface/v1.5",      // if this extends another FF
  "overrides": [                            // declared intentional overrides
    {"target": "cvff-interface/v1.5", "scope": "bonds", "reason": "DFT benchmark"}
  ],
  "renames": {"old_type": "new_type"},      // atom type renames since `supersedes`
  "breaking": false,
  "partial_roundtrip": false                 // true if parser can't fully roundtrip source
}
```

### 4.3 Structure Entry additional fields

```json
{
  "atom_type_family": "cvff-mxene-additions",
  "parameterized_with": [                    // always a list; single-FF is list of 1
    {"name": "cvff-mxene-additions", "version": "v1.0"}
  ],
  "charges_source": "structure",             // or "ff"; default "structure"
  "lock_to_original": false,                 // if true, pull_latest refuses
  "validated_with": [                        // optional post-hoc annotations
    {"name": "cvff-mxene-additions", "version": "v1.1"}
  ],
  "geometry": {
    "path": "geometry/source.car",
    "format": "car",
    "n_atoms": 120,
    "sha256": "..."
  },
  "atoms_csv": {"path": "atoms.csv", "rows": 120, "sha256": "..."}
}
```

## 5. Pull semantics

Three well-defined operations over the immutable store:

| Operation | Returns |
|---|---|
| `pull_latest(structure_id)` | structure + newest non-deprecated compatible version of `atom_type_family`. Default in UI. Applies renames automatically. |
| `pull_original(structure_id)` | structure + exact `parameterized_with` pin. Historical fidelity. |
| `pull_version(structure_id, target_version)` | structure + specified version, subject to compatibility check. |

### 5.1 Compatibility check algorithm

Given structure `S` (using atom types, bond keys, angle keys, torsion keys) and target FF version `F@V_t`:

1. Collect required keys from `S` (from its `atoms.csv` + `topology.csv`).
2. Walk the rename chain from `S.parameterized_with.version` forward to `V_t`, composing all `renames` maps.
3. Apply composed rename map to required keys.
4. Compute missing keys against `F@V_t`'s tables.
5. Check if any version between the pin and target has `breaking: true`.
6. Return `CompatibilityResult{status, renames_applied, missing, breaking_crossed, fallback_version}`.

Status is `OK` (no missing keys), `WARNING` (breaking crossed but no missing keys), or `ERROR` (missing keys).

### 5.2 Fallback

- `pull_latest` with status `ERROR`: walk backwards from latest, return first version that passes. UI banner: "Latest v1.2 incompatible (missing 'ti4f'). Returning v1.1."
- `pull_latest` on an entry with `lock_to_original: true`: returns original + banner "pinned by author".
- `pull_version` with `ERROR`: operation fails with explicit error. No silent fallback.

## 6. Consistency invariants (CI-enforced)

1. **Immutability**: once a version directory appears in a merged commit on `main`, its contents never change. Fixes → new version.
2. **Referential integrity**: every `parameterized_with`, `supersedes`, `parent_ff`, `overrides.target`, `validated_with` reference must resolve.
3. **No duplicate versions**: within a family, version strings are unique.
4. **Atom type coverage**: every atom type used in a structure's `atoms.csv` must exist (possibly after rename) in its `parameterized_with` FF version.
5. **Hash integrity**: every declared sha256 matches actual file contents.
6. **Provenance required**: `provenance.author` and `provenance.source_sha256` set.
7. **Schema version honored**: entries declare `schema_version`; validators check against that version's schema.

## 7. What lives in manifests vs. git

| Concern | Manifest | Git |
|---|---|---|
| Content of each version | ✓ | — |
| Scientific authorship | ✓ (`provenance.author`) | — |
| Commit pusher | — | ✓ (commit author) |
| When version added to repo | — | ✓ (commit date) |
| Semantic relationships (supersedes, parent_ff, renames) | ✓ | — |
| Rationale | ✓ (`provenance.notes`) + ✓ (commit message) | ✓ |
| Diff between versions | derived | ✓ (`git diff`) |
| Rollback of accidents | — | ✓ (`git revert`) |

## 8. Discovery

Entries are discovered via Python entry-points in the `upm.data_packages` group. The iff-parameters package registers `iff = "iff_parameters:get_data_dir"` → path to `src/iff_parameters/data/`.

External projects (`iff-mxene`, `iff-ceramic-surfaces`, ...) can each register their own entry-point in the same group. UPM's `registry.discovery.discover_packages()` aggregates all registered packages at runtime.

The dashboard builds a live in-memory index:
- `atom_type_index`: type → [entries]
- `bond_index`, `angle_index`, `torsion_index`: tuple → [entries]
- `material_coverage`: material → [(parameters, structures)]
- `conflict_list`: cross-entry key collisions with value disagreements

Index rebuilds on upload via `st.cache_data.clear()`.

## 9. Conflict resolution

A conflict = two entries with the same key but different values **at the same point in library time**. Cross-version evolution of one family (v1.0 → v1.1) is NOT a conflict.

Each conflict is resolved via one of:
1. **Override** — newer entry declares `overrides: [...]`. Explicit, acknowledged. Both entries coexist.
2. **Deduplication** — identical values → harmless duplicate, noted, no action.
3. **Fork** — two entries intentionally diverge (e.g., basal vs. edge MXene). Different family names.

Unresolved conflicts trigger CI warnings but don't block merges — they surface in the dashboard's Conflicts page for human review.

## 10. Upload flow

1. User drops `.frc`/`.prm`/`.car`/`.mdf`/`.pdb` in dashboard.
2. Parser extracts tables; format detected from extension.
3. Dashboard runs conflict/overlap detection against live index.
4. User sees preview report: new keys, collisions (harmless vs. disagreement), similarity to existing entries.
5. User declares intent: new bundle / new version of existing / override / fork.
6. For structures: user selects `parameterized_with` from a dropdown of existing parameter entries.
7. Dashboard writes entry to `data/` (local runs) or packages a ready-to-commit zip (hosted).
8. User commits and opens PR; CI validates; merge.

## 11. Migration from v0.1.0

- Existing four bundles move to `data/archive/` (preserved, excluded from discovery).
- Seeded from INTERFACE_FF_1_5: `cvff-interface/v1.5`, `pcff-interface/v1.5` (with `partial_roundtrip: true`), `charmm27-interface/v1.5`.
- MODEL_DATABASE ingested as ~341 Structure Entries organized by material class.
- Dashboard updated; new pages (Conflicts, Coverage, Structures).

Migration is a one-time seed run documented in `scripts/seed_from_interface_ff15.py`.
