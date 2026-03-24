# IFF Ecosystem Backlog

## Status Key
- `DONE` — Completed and deployed
- `IN PROGRESS` — Currently being worked on
- `BACKLOG` — Planned, not started
- `DEFERRED` — Deprioritized, revisit later

## Completed

| Item | Package | Date | Notes |
|------|---------|------|-------|
| UPM v2.0 | upm | 2026-03-24 | .frc + .prm codecs, registry, 9 CLI commands, 179 tests |
| USM v2.0 | usm | 2026-03-24 | PDB import, unified loader, 69 tests |
| iff-parameters v0.1.0 | iff-parameters | 2026-03-24 | 4 public bundles, ingest scripts, similarity detection |
| CONTRIBUTING.md + PR template | iff-parameters | 2026-03-24 | Lab workflow documented |
| Branch protection | iff-parameters | 2026-03-24 | Require PR + CI |
| Cross-package integration tests | iff-parameters | 2026-03-24 | USM → UPM → iff-params pipeline |
| Layer composition system | upm | 2026-03-24 | stack_layers + export monolithic .frc/.prm |
| MOLSAIC v2.0 alignment | molsaic | 2026-03-24 | Umbrella updated to v2.0 |

## In Progress

| Item | Package | Priority | Notes |
|------|---------|----------|-------|
| Streamlit web dashboard | iff-dashboard | HIGH | PI wants browsable FF portal on lab website |

## Backlog

| Item | Package | Priority | Effort | Notes |
|------|---------|----------|--------|-------|
| GROMACS .itp export | upm | MEDIUM | 1 week | IFF-R runs 3-6x faster in GROMACS |
| PCFF codec (9-6 LJ, cross-terms) | upm | MEDIUM | 2 weeks | Schemas defined, parsers not done |
| Ingest pcff_interface_v1_5.frc | iff-parameters | LOW | 1 day | Blocked on PCFF parser |
| UPM torsion/dihedral resolver | upm | LOW | 3 days | Schema done, resolver stubs all as missing |
| CIF symmetry expansion in USM | usm | MEDIUM | 1 week | Partial stub exists, needed for real crystals |
| Ingest pcff_interface_v1_5.off | iff-parameters | LOW | — | New format, Materials Studio typing rules |
| Auto-equivalence table support | upm | LOW | 3 days | Schema defined, parser not done |
| USM GROMACS .gro format | usm | LOW | 3 days | For GROMACS workflows |
| USM .xyz format | usm | LOW | 1 day | Simple format, easy to add |
| Zenodo DOI for iff-parameters | iff-parameters | MEDIUM | 1 day | Proper citation for publications |
