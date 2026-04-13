# IFF Parameters — Validation Plan

**Status:** Proposed
**Companion to:** `ARCHITECTURE.md`, `USE_CASES.md`

Purpose: systematically verify every use case (UC) and edge case (EC) from `USE_CASES.md` before declaring the rebuild done. Each section maps to test categories with acceptance criteria.

---

## 1. Test categories

| Category | What it tests | Framework | Where |
|---|---|---|---|
| **Unit (UPM)** | Individual UPM functions (codecs, core, bundle, registry, compose) | `pytest` | `MOLSAICV4/src/upm/tests/` |
| **Unit (iff-parameters)** | Manifest parsing, compatibility check, pull operations, indexing | `pytest` | `iff-parameters/tests/` |
| **Integration** | End-to-end flows: seed, upload, pull, conflict detection | `pytest` | `iff-parameters/tests/integration/` |
| **UI** | Dashboard behavior per page | `streamlit.testing.v1.AppTest` (built-in Streamlit test harness) | `iff-parameters/tests/ui/` |
| **CI / Validate** | Schema + referential integrity enforced on PRs | `scripts/validate.py` called from GitHub Action | `iff-parameters/scripts/` + `.github/workflows/` |
| **Seed validation** | Seed script produces correct bundle layout from INTERFACE_FF_1_5 | integration test | `iff-parameters/tests/integration/test_seed.py` |
| **Manual acceptance** | Human smoke tests for things that can't be automated | checklist | `docs/ACCEPTANCE_CHECKLIST.md` (created at cutover) |

## 2. Acceptance criteria

Before declaring the rebuild done:
- 100% of use cases (UC-1…UC-14) have a passing integration test.
- 100% of edge cases (EC-1…EC-25) have at least one test.
- Unit test coverage for new code ≥ 80% (measured by `pytest --cov`).
- CI green on Python 3.10, 3.11, 3.12, 3.13.
- Ruff + mypy clean on changed modules.
- Seeded library passes `validate.py` with zero errors, zero warnings.
- Dashboard manually walked through per `ACCEPTANCE_CHECKLIST.md`, all items ticked.

## 3. Unit tests

### 3.1 UPM codecs

| ID | Test | Module |
|---|---|---|
| U-C-1 | `parse_frc_text` roundtrips CVFF canonical | `test_msi_frc.py` |
| U-C-2 | `parse_frc_text` on PCFF reports partial_roundtrip=True, preserves raw | `test_msi_frc_pcff.py` |
| U-C-3 | `parse_prm_text` roundtrips CHARMM27 canonical | `test_charmm_prm.py` |
| U-C-4 | Writer produces byte-identical output for CVFF roundtrip | `test_msi_frc.py` |
| U-C-5 | Unknown sections preserved in order | `test_roundtrip_unknown.py` |

### 3.2 UPM core tables

| ID | Test | Notes |
|---|---|---|
| U-T-1 | `normalize_tables` imposes canonical column order | |
| U-T-2 | `normalize_tables` canonicalizes bond/angle/torsion keys (sorted tuples) | |
| U-T-3 | `normalize_tables` is idempotent (normalize(normalize(x)) == normalize(x)) | |
| U-T-4 | LJ A-B ↔ sigma-epsilon conversion roundtrips (rtol=1e-6) | |

### 3.3 UPM bundle I/O

| ID | Test | Notes |
|---|---|---|
| U-B-1 | `save_package` → `load_package` roundtrips all tables | |
| U-B-2 | Manifest schema version honored on load | EC-19 |
| U-B-3 | `save_package` with `partial_roundtrip=True` sets manifest flag | EC-17 |
| U-B-4 | Hash mismatch raises at load | EC-18 |
| U-B-5 | Missing required fields raises ValidationError | inv #6 |

### 3.4 UPM registry + compose

| ID | Test | Notes |
|---|---|---|
| U-R-1 | `discover_packages()` aggregates entry points across installed packages | UC-11 |
| U-R-2 | `diff_tables` returns ParameterDiff with added/removed/changed types | UC-8 |
| U-R-3 | `PackageIndex` builds key-level indexes (atom, bond, angle, torsion) | §8 spec |
| U-R-4 | `stack_layers` last-writer-wins with bundle-level provenance chain | UC-14 |
| U-R-5 | Rename-aware compatibility: composed rename map across chain | EC-1, EC-14 |

### 3.5 iff-parameters compatibility check

| ID | Test | Notes |
|---|---|---|
| U-CC-1 | `compatibility_check(S, F@V_t)` OK when all keys present | UC-5 |
| U-CC-2 | WARNING when breaking crossed but keys present | EC-3 |
| U-CC-3 | ERROR when atom type missing and no rename | EC-2 |
| U-CC-4 | Renames composed across version chain | EC-1 |
| U-CC-5 | Fallback returns highest compatible version | EC-2 |
| U-CC-6 | lock_to_original forces pull_latest to return original | EC-12 |
| U-CC-7 | Deprecated versions skipped in pull_latest | EC-4, UC-13 |
| U-CC-8 | Multi-family `parameterized_with` resolves each independently | EC-5 |

### 3.6 iff-parameters pull operations

| ID | Test | Notes |
|---|---|---|
| U-P-1 | `pull_latest` returns newest + resolution metadata | UC-5 |
| U-P-2 | `pull_original` returns exact pin | UC-6 |
| U-P-3 | `pull_version(X)` returns X on compatibility OK, fails on ERROR | UC-7 |
| U-P-4 | Pull outputs charges from structure atoms.csv, FF tables merged | §5, §4.3 |

## 4. Integration tests

Each UC gets an `test_uc_<n>_*.py`. Tests use `tmp_path` fixtures, write real bundles, call real discovery, and assert end-to-end behavior.

| UC | Test file | Acceptance |
|---|---|---|
| UC-1 | `test_uc_1_seed.py` | Seed produces 3 param + ~341 structure entries, all validated |
| UC-2 | `test_uc_2_new_family.py` | New family written, discoverable, indexed |
| UC-3 | `test_uc_3_new_version.py` | v1.1 written with supersedes; v1.0 intact; diff visible |
| UC-4 | `test_uc_4_structure_upload.py` | Structure written, pinned, atom-type coverage check passes |
| UC-5 | `test_uc_5_pull_latest.py` | Default pull returns latest + banner metadata |
| UC-6 | `test_uc_6_pull_original.py` | Returns exact pin |
| UC-7 | `test_uc_7_pull_version.py` | Specific version or explicit failure |
| UC-8 | `test_uc_8_compare.py` | Diff reports added/removed/changed |
| UC-9 | `test_uc_9_browse.py` | Material filter produces union of params + structures |
| UC-10 | `test_uc_10_coverage.py` | Coverage grid correct for seeded library |
| UC-11 | `test_uc_11_multi_package.py` | Two entry-point packages discovered |
| UC-12 | `test_uc_12_annotate.py` | Validated_with annotations persist |
| UC-13 | `test_uc_13_deprecate.py` | Deprecated version skipped by pull_latest |
| UC-14 | `test_uc_14_override.py` | Override manifest recorded, conflicts page shows it |

## 5. Edge case tests

Each EC → `test_ec_<n>_*.py`.

| EC | Test | Primary assertion |
|---|---|---|
| EC-1 | `test_ec_1_rename.py` | pull_latest succeeds with auto-rename applied |
| EC-2 | `test_ec_2_removed_type.py` | pull_latest falls back to last compatible version |
| EC-3 | `test_ec_3_breaking.py` | pull_latest stops at last pre-breaking version |
| EC-4 | `test_ec_4_deprecated.py` | Deprecated skipped in latest walk |
| EC-5 | `test_ec_5_multi_family.py` | Independent resolution per family |
| EC-6 | `test_ec_6_duplicate_version.py` | Duplicate blocked by validate.py |
| EC-7 | `test_ec_7_forward_ref.py` | Broken reference caught by CI |
| EC-8 | `test_ec_8_deletion.py` | Missing version referenced → CI fail |
| EC-9 | `test_ec_9_missing_type.py` | Structure type not in FF → upload rejected |
| EC-10 | `test_ec_10_charge_variants.py` | Two structures with different charges coexist |
| EC-11 | `test_ec_11_original_was_latest.py` | Given pin + commit date → reproducible "latest at upload" |
| EC-12 | `test_ec_12_lock_to_original.py` | pull_latest returns original, banner shown |
| EC-13 | `test_ec_13_fork.py` | Two fork families coexist; old structure untouched |
| EC-14 | `test_ec_14_rename_plus_removal.py` | Partial compatibility: some types rename, one is removed |
| EC-15 | `test_ec_15_conflicting_overrides.py` | Both overrides recorded; conflict page shows both |
| EC-16 | `test_ec_16_amend_metadata.py` | Metadata-only amendment allowed if tables unchanged |
| EC-17 | `test_ec_17_pcff_partial.py` | PCFF bundle ingested with partial_roundtrip=True, raw preserved |
| EC-18 | `test_ec_18_hash_mismatch.py` | CI fails on tampered CSV |
| EC-19 | `test_ec_19_schema_version.py` | Loader handles multiple schema versions |
| EC-20 | `test_ec_20_missing_package.py` | Unresolvable family → clear error |
| EC-21 | `test_ec_21_unicode.py` | UTF-8 author names roundtrip; atom types reject special chars |
| EC-22 | `test_ec_22_large_structure.py` | 100k-atom upload under 60s (perf budget) |
| EC-23 | `test_ec_23_concurrent_uploads.py` | Two PRs with same version → second fails CI |
| EC-24 | `test_ec_24_cycle.py` | Circular supersedes → CI fail |
| EC-25 | `test_ec_25_empty_table.py` | 0-row tables allowed |

## 6. UI tests (Streamlit AppTest)

Covers dashboard pages. Each test launches the app in a subprocess, performs clicks, asserts outputs.

| ID | Test | Page | Scenario |
|---|---|---|---|
| UI-1 | Home loads | `app.py` | Stats match seeded library |
| UI-2 | Search by atom type | `1_Search.py` | Matches across families |
| UI-3 | Browse entries | `2_Browse.py` | Parameters and structures both visible; linkage navigation works |
| UI-4 | Compare versions | `3_Compare.py` | Diff rendered for v1.0 vs v1.1 |
| UI-5 | Download (latest) | `4_Download.py` | Default pull returns latest zip |
| UI-6 | Download (original) | `4_Download.py` | Explicit original option returns pinned version |
| UI-7 | Upload parameters | `5_Upload.py` | Conflict preview shown, ingest writes entry |
| UI-8 | Upload structure | `6_Upload_Structure.py` | parameterized_with dropdown populated, coverage check gates ingest |
| UI-9 | Conflicts page | `7_Conflicts.py` | Cross-entry collisions listed |
| UI-10 | Coverage page | `8_Coverage.py` | Grid of material × family |

## 7. CI / `validate.py` tests

`scripts/validate.py` is run on every PR. It must:

| ID | Check | Enforces |
|---|---|---|
| V-1 | All manifests parse and match their declared `schema_version` | inv #7 |
| V-2 | Every `parameterized_with` reference resolves | inv #2, EC-7 |
| V-3 | Every `supersedes`, `parent_ff`, `overrides.target`, `validated_with` resolves | inv #2 |
| V-4 | No duplicate `<family>@<version>` | inv #3, EC-6 |
| V-5 | Every table sha256 matches file | inv #5, EC-18 |
| V-6 | Atom type coverage: structure atoms.csv ⊆ (FF atom_types ∪ renames) | inv #4, EC-9 |
| V-7 | No circular `supersedes` chain | EC-24 |
| V-8 | No breaking change crossed without `breaking: true` declared | inv, EC-3 |
| V-9 | Unresolved cross-entry conflicts surface as warnings (not errors) | §9 |
| V-10 | Immutability check: a modified commit cannot edit existing table CSVs (only add new version dirs) | inv #1 |

Tests under `tests/ci/test_validate_*.py` construct pathological fixtures and assert `validate.py` fails/passes correctly.

## 8. Seed validation

`scripts/seed_from_interface_ff15.py` must:

| ID | Assertion |
|---|---|
| S-1 | Produces exactly 3 parameter entries from canonical_sources/INTERFACE_FF_1_5/FORCE_FIELDS/ |
| S-2 | PCFF entry has `partial_roundtrip: true`; raw source preserved |
| S-3 | Structure entries for all 341 MODEL_DATABASE files; material_class correctly assigned |
| S-4 | Each structure has `parameterized_with` correctly inferred from `.mdf` / filename conventions |
| S-5 | All structure entries pass atom-type coverage check against their pinned FF |
| S-6 | Seeded library as a whole passes `validate.py` with 0 errors |
| S-7 | Seed is idempotent (running twice produces identical output) |
| S-8 | Seed is reversible (a `rollback_seed.py` restores prior state from archive/) |

## 9. Manual acceptance checklist

For cutover, human walks through `docs/ACCEPTANCE_CHECKLIST.md` (to be written). Samples:

- [ ] Run dashboard locally, browse home page — stats match expected seeded counts
- [ ] Click a silica structure → see pinned FF, click through → see FF's tables
- [ ] Upload a test `.frc` with known conflicts — preview report matches manual diff
- [ ] Upload a test structure with `parameterized_with` for a known FF — succeeds
- [ ] Upload a structure with a missing atom type — rejected with clear error
- [ ] Deploy to Streamlit Cloud — dashboard loads, read-only paths work
- [ ] Open a conflict in Conflicts page, click "resolve" — link opens GitHub issue with pre-filled body
- [ ] Deprecate a version through dashboard — commit produced, CI green, pull_latest skips it
- [ ] Clone repo fresh, follow CONTRIBUTING.md — `pip install -e .`, run tests, all pass

## 10. Performance budgets

| Operation | Budget | Rationale |
|---|---|---|
| Dashboard cold load | < 3s | Seeded library of ~350 entries |
| Index rebuild after upload | < 1s | Keeps upload UX responsive |
| Pull operation (pull_latest w/ compat check) | < 500ms | Bounded by table CSV read |
| Seed script from INTERFACE_FF_1_5 | < 60s | Run-once-ish but pain if slow |
| CI `validate.py` on full library | < 30s | Fast PR feedback |
| Large structure ingest (100k atoms) | < 10s parse + write | EC-22 |

Measured with `pytest-benchmark` or timed in CI. Regressions block merge.

## 11. Rollout plan

1. Land ARCHITECTURE + USE_CASES + VALIDATION_PLAN on a feature branch (`v0.2-rebuild`).
2. Implement Phase 2 (UPM schema extensions) on MOLSAICV4 v2-refactor branch; PR + merge.
3. Implement Phase 3 (seed scripts); run in isolation on feature branch; iterate.
4. Implement Phase 4 (dashboard updates); validate against seeded data.
5. Implement Phase 5 (tests covering every UC + EC).
6. Run full validation suite; walk acceptance checklist.
7. Archive existing 4 bundles on main → seed branch merges to main → tag v0.2.0.
8. Update deployed Streamlit app; announce to group.

No "big bang" replacement — the rebuild lives on a feature branch until all of §2 is green.
