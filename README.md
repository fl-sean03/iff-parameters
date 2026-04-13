<h1 align="center">IFF Parameters</h1>

<p align="center">
  <strong>Central library of force-field parameters + pre-parameterized structures for the INTERFACE Force Field</strong>
</p>

<p align="center">
  <a href="https://iff-parameters-hhl.streamlit.app"><img src="https://img.shields.io/badge/Dashboard-Live-brightgreen?logo=streamlit" alt="Dashboard"></a>
  <a href="https://github.com/fl-sean03/iff-parameters/actions"><img src="https://github.com/fl-sean03/iff-parameters/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://img.shields.io/badge/python-3.10%2B-blue"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python"></a>
  <a href="https://doi.org/10.1021/la3038846"><img src="https://img.shields.io/badge/IFF%20Paper-Langmuir%202013-green" alt="Paper"></a>
</p>

<p align="center">
  Single, versioned, git-tracked database of IFF parameter sets and the
  structures they were used to parameterize.<br>
  Built on <a href="https://github.com/fl-sean03/upm">UPM v2.1</a> (parameter toolkit) and
  <a href="https://github.com/fl-sean03/usm">USM</a> (structure toolkit).
</p>

---

## What's in the library

The library holds two kinds of **entries**:

- **Parameter entries** — `.frc` / `.prm` force field files, parsed into
  canonical CSV tables + raw source + provenance.
- **Structure entries** — pre-parameterized molecular geometries (one or
  more `.car` / `.mdf` / `.pdb` files) with per-atom FF types and charges,
  pinned to exact parameter versions.

Every entry is an immutable versioned directory. New versions create new
directories; existing versions never change after publish. This gives you
reproducibility + history for free without a database backend.

### Seeded from INTERFACE_FF_1_5

The baseline is the Hendrik Heinz INTERFACE Force Field v1.5 distribution:

| Parameter family | Format | Atom types | Notes |
|---|---|---|---|
| `cvff-interface/v1.5` | CVFF | 180 | canonical CVFF-based IFF |
| `pcff-interface/v1.5` | PCFF | 214 | partial roundtrip — 9-6 nonbond and cross-term sections preserved as raw |
| `charmm27-interface/v1.5` | CHARMM | 166 | for NAMD / OpenMM |

Plus **133 pre-parameterized structures** across 7 material classes:
silica (24), metals (32), cement (28), clay (24), hydroxyapatite (20),
Ca-sulfate (3), PEO (2).

---

## Mental model

### Pull operations

When someone wants a structure plus its parameters, three operations are
defined:

| Operation | Returns |
|---|---|
| `pull_latest(structure)` | structure + newest non-deprecated compatible version of its FF family. **Default.** Auto-applies renames; walks backward on incompatibility. |
| `pull_original(structure)` | structure + exact `parameterized_with` pin. Historical fidelity. |
| `pull_version(structure, fam, ver)` | explicit; no silent fallback. |

A structure pins to the exact FF version it was built against. When the
FF gets refined (e.g., `v1.0 → v1.1` with better bond values, same atom
type names), `pull_latest` picks up those improvements automatically.
When atom types are renamed, the target FF declares a `renames` map and
the pull auto-applies it. When something incompatible happens, the pull
either falls back (`pull_latest`) or fails loudly (`pull_version`).

### What triggers a new version

| Change | New FF version? | New structure version? |
|---|---|---|
| FF refined values (same atom-type names) | ✅ | ❌ |
| FF renamed atom types (declared in `renames`) | ✅ | ❌ (auto-migrated) |
| FF removed an atom type the structure uses | ✅ | only if you relabel |
| Structure geometry changed | ❌ | ✅ |
| Structure atom labels changed | ❌ | ✅ |
| Structure atomic charges re-fitted | ❌ | ✅ |

Charges live with the structure file, not the FF. The FF updates values
behind atom-type labels; structures own the charge assignments.

### Conflict detection

When you upload a new parameter entry, the dashboard parses it, compares
against every existing entry, and shows:

- **Harmless duplicates** (same key, identical values) — noted, no action.
- **Real disagreements** (same key, different values) — flagged. You
  declare intent: new family / new version / intentional override / fork.

See `docs/USE_CASES.md` for all 14 use cases + 25 edge cases, and
`docs/ARCHITECTURE.md` for the full spec.

---

## Quick start

```bash
pip install "git+https://github.com/fl-sean03/upm.git@main"
pip install "git+https://github.com/fl-sean03/usm.git@main"   # optional
pip install -e .

# Seed the library from INTERFACE_FF_1_5 (if you have the distribution)
python scripts/seed_from_interface_ff15_parameters.py
python scripts/seed_from_interface_ff15_structures.py

# Launch the dashboard
streamlit run dashboard/app.py
```

### Find parameters for a material

```python
from iff_parameters import search_by_material
for r in search_by_material("silica"):
    print(f"{r['type']:10}  {r['ref']}  ({r['format']})")
```

### Browse parameter + structure entries

```python
from iff_parameters.entries import list_parameter_entries, list_structure_entries
print(f"Parameters: {len(list_parameter_entries())}")
print(f"Structures: {len(list_structure_entries())}")
```

### Pull a structure with latest compatible parameters

```python
from iff_parameters.entries import iter_entries
from iff_parameters.pull import pull_latest

for s in iter_entries("structure"):
    r = pull_latest(s)
    print(f"{s.ref():40}  {r.status}  resolved={list(r.parameters)}")
    break
```

### Validate the library

```bash
python scripts/validate.py
# runs V-1..V-10 (schema, references, hashes, coverage, cycles, ...)
```

### Compare two parameter versions

```python
from iff_parameters.entries import find_parameter_entry
from upm.bundle.io import load_package
from upm.registry.diff import diff_tables

a = load_package(find_parameter_entry("cvff-interface", "v1.5").path)
b = load_package(find_parameter_entry("pcff-interface", "v1.5").path)
diff = diff_tables(a.tables, b.tables)
print(diff.summary())
```

---

## Dashboard

Live: [iff-parameters-hhl.streamlit.app](https://iff-parameters-hhl.streamlit.app)

| Page | What it does |
|---|---|
| **Home** | Library metrics + tabbed parameter/structure overview |
| **Search** | Cross-family search by atom type or material |
| **Browse** | Parameters ↔ structures cross-linked |
| **Compare** | Side-by-side diff of two parameter versions |
| **Download** | `pull_latest` / `pull_original` / `pull_version` of structure + parameters as a zip |
| **Upload** | Ingest a new `.frc` / `.prm` with conflict preview + intent declaration |
| **Upload Structure** | Ingest a pre-parameterized `.car` with auto family-detection |
| **Conflicts** | Cross-entry key collisions that disagree on values |
| **Coverage** | Materials × families grid, gap + staleness flags |

Local:

```bash
streamlit run dashboard/app.py
```

> **Deployed dashboard is read-only for uploads.** Streamlit Community
> Cloud has an ephemeral filesystem — uploads survive only until the
> container restarts. For durable writes, clone locally and PR.

---

## Architecture

```
iff-parameters/
├── src/iff_parameters/
│   ├── __init__.py              # get_data_dir(), list_available(), search_by_material()
│   ├── entries.py               # Entry + Version + iter_entries + index_family_versions
│   ├── compat.py                # compatibility_check() with rename-chain composition
│   ├── pull.py                  # pull_latest / pull_original / pull_version
│   ├── _provenance.py           # legacy Provenance dataclass (v0.1.x)
│   └── data/
│       ├── parameters/
│       │   └── <family>/<version>/
│       │       ├── manifest.json     # lineage, overrides, renames, hashes
│       │       ├── tables/*.csv
│       │       └── raw/source.{frc,prm}
│       ├── structures/
│       │   └── <material>/<model>/<version>/
│       │       ├── manifest.json     # parameterized_with, lock_to_original
│       │       ├── atoms.csv
│       │       └── geometry/source.car
│       └── archive/                  # v0.1.0 bundles; not discoverable
├── scripts/
│   ├── seed_from_interface_ff15_parameters.py
│   ├── seed_from_interface_ff15_structures.py
│   ├── validate.py                   # V-1..V-10 validator
│   └── check_immutability.py         # PR advisory
├── dashboard/                        # Streamlit app (app.py + pages/)
├── docs/
│   ├── ARCHITECTURE.md               # authoritative spec
│   ├── USE_CASES.md                  # 14 UCs + 25 ECs with expected behavior
│   ├── VALIDATION_PLAN.md            # test matrix
│   └── ACCEPTANCE_CHECKLIST.md       # cutover smoke test
└── tests/
    ├── integration/                  # UC/EC/seed/validator/perf tests
    └── ui/                           # Streamlit AppTest smokes
```

### Provenance captured per entry

| Field | Example |
|---|---|
| `author` | Hendrik Heinz |
| `source_sha256` | `9c1f7aff…` |
| `publication_doi` | `10.1021/la3038846` |
| `parent_ff` | `cvff-interface/v1.5` |
| `supersedes` | `v1.0` |
| `renames` | `{"ti4f": "ti4fh"}` |
| `materials` | `["silica", "clays"]` |
| `ingested_utc` | `2026-04-13T15:47:00Z` |

---

## Adding parameters (or structures)

### Dashboard upload (local clone, then PR)

1. Clone the repo, run `streamlit run dashboard/app.py`
2. Upload → parse → review the conflict preview (disagreements vs.
   harmless duplicates) → declare intent → ingest writes to `data/`
3. Commit the new version directory, open a PR
4. CI (`validate.py`) gates the merge

### CLI ingest

```bash
# not yet implemented — see BACKLOG. For now, use the dashboard or
# call upm.bundle.io.save_package directly from a script.
```

---

## Citation

If you use these parameters in published work, please cite:

> Heinz, H.; Lin, T.-J.; Mishra, R. K.; Emami, F. S. "Thermodynamically
> Consistent Force Fields for the Assembly of Inorganic, Organic, and
> Biological Nanostructures: The INTERFACE Force Field." *Langmuir*
> **2013**, 29, 1754–1765. [DOI: 10.1021/la3038846](https://doi.org/10.1021/la3038846)

Individual entries may have additional citations — check
`manifest.json → provenance → publication_doi`.

---

## Related projects

| Project | Description |
|---|---|
| [UPM](https://github.com/fl-sean03/upm) | Unified Parameter Model — parses/writes `.frc`/`.prm`, manifests, registry, compose |
| [USM](https://github.com/fl-sean03/usm) | Unified Structure Model — CAR/MDF/CIF/PDB |
| [INTERFACE FF](https://github.com/hendrikheinz/INTERFACE-force-field-and-surface-models) | Official IFF v1.5 distribution |

---

<p align="center">
  <sub>Developed at the <a href="https://bionanostructures.com/">Heinz Lab</a>, University of Colorado Boulder</sub>
</p>
