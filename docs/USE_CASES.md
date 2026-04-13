# IFF Parameters — Use Cases and Edge Cases

**Status:** Proposed
**Companion to:** `ARCHITECTURE.md`

Each case has: **Preconditions**, **Action**, **Expected behavior**, **Error/edge notes**. Drives `VALIDATION_PLAN.md`.

---

## Normal use cases

### UC-1: Seed the library from INTERFACE_FF_1_5
- **Preconditions:** Empty `data/` (old bundles archived). INTERFACE_FF_1_5 available at `canonical_sources/`.
- **Action:** Run `scripts/seed_from_interface_ff15.py`.
- **Expected:** Creates 3 Parameter Entries (cvff-interface/v1.5, pcff-interface/v1.5, charmm27-interface/v1.5) and ~341 Structure Entries across 7 material classes. PCFF bundle has `partial_roundtrip: true`. All manifests pass validation. CI is green.

### UC-2: Add a new parameter set (new family)
- **Preconditions:** Library seeded. User has a `.frc` file for MXene additions.
- **Action:** Drag `.frc` into dashboard Upload → declare new family `cvff-mxene-additions`, version `v1.0`, author metadata. Conflict preview shows 3 atom types overlap with cvff-interface@v1.5 (identical values → harmless).
- **Expected:** Entry written to `parameters/cvff-mxene-additions/v1.0/`. Provenance captured. Manifest references are resolvable. Dashboard Browse shows new entry. Key-level index updated.

### UC-3: Update a parameter value (new version of existing family)
- **Preconditions:** `cvff-mxene-additions/v1.0` exists with Ti-O bond k=300.
- **Action:** Upload refined `.frc` with k=280. Declare as new version `v1.1` of existing family. Conflict preview shows (ti, o) bond disagrees with v1.0 — user marks "intentional refinement".
- **Expected:** Written to `parameters/cvff-mxene-additions/v1.1/` with `supersedes: "v1.0"`. v1.0 untouched. Both versions queryable. Compare page shows diff.

### UC-4: Upload a structure pinned to a parameter version
- **Preconditions:** `cvff-mxene-additions/v1.0` exists.
- **Action:** Upload `Ti3C2_F-term.car` + `.mdf` via Structure Upload. Select "parameterized with: cvff-mxene-additions@v1.0".
- **Expected:** Written to `structures/mxene/Ti3C2_F-term/v1.0/`. `parameterized_with: [{name: "cvff-mxene-additions", version: "v1.0"}]`. Per-atom charges from `.car` preserved in `atoms.csv`. `charges_source: "structure"`. Atom-type coverage check passes.

### UC-5: Pull a structure with latest parameters (default)
- **Preconditions:** Structure `Ti3C2_F-term/v1.0` pinned to `cvff-mxene-additions@v1.0`. FF bumped to v1.1 (same atom type names, refined bond values).
- **Action:** Dashboard → Structure entry → click "Download (latest)".
- **Expected:** Compatibility check passes. Returns structure file + cvff-mxene-additions@v1.1 tables. UI banner: "resolved to v1.1 (original was v1.0)".

### UC-6: Pull a structure with original parameters (historical)
- **Preconditions:** Same as UC-5.
- **Action:** Click "Download (original parameters)".
- **Expected:** Returns structure file + cvff-mxene-additions@v1.0 tables. Banner: "original pin, v1.0".

### UC-7: Pull a structure with specific parameter version
- **Preconditions:** Versions v1.0, v1.1, v1.2 exist. Structure pinned to v1.0.
- **Action:** Click "Download (select version)" → choose v1.1.
- **Expected:** Compatibility check against v1.1. If OK, returns structure + v1.1. If ERROR, explicit failure message (no silent fallback).

### UC-8: Compare two FF versions side-by-side
- **Preconditions:** cvff-mxene-additions v1.0 and v1.1 both exist.
- **Action:** Dashboard → Compare → select v1.0 and v1.1.
- **Expected:** Tables show added/removed atom types, changed bond/angle/torsion parameters with numeric diffs.

### UC-9: Browse library by material
- **Preconditions:** Seeded library.
- **Action:** Dashboard → Browse → filter by "SILICA".
- **Expected:** Shows all parameter entries covering silica + all structure entries whose `material_class = silica`. Clicking a structure shows its pinned parameters; clicking a parameter shows structures using it.

### UC-10: Detect coverage gaps
- **Preconditions:** Seeded library.
- **Action:** Dashboard → Coverage page.
- **Expected:** Material × FF grid. Each cell shows: entry count, newest version, age. Empty cells flagged as gaps. Stale cells (>2 years) flagged.

### UC-11: Cross-project discovery via entry points
- **Preconditions:** iff-parameters installed. Separate package `iff-mxene-v2` also installed, registering `upm.data_packages.mxene`.
- **Action:** `discover_packages()`.
- **Expected:** Returns entries from both packages, flat list. Dashboard indexes both.

### UC-12: Annotate post-hoc compatibility
- **Preconditions:** Structure `Ti3C2_F-term/v1.0` pinned to cvff-mxene-additions@v1.0. User manually validates simulation with v1.2.
- **Action:** Dashboard → Structure → "Add validation annotation" → pick v1.2.
- **Expected:** Manifest `validated_with: [{name, version: "v1.2"}]` updated (via new commit). Dashboard shows green check next to v1.2 on structure page.

### UC-13: Deprecate a parameter version
- **Preconditions:** v1.0 superseded by v1.1 and author wants to steer users.
- **Action:** Amend v1.0's manifest with `deprecated: true, deprecation_reason: "refined in v1.1"` (new commit, no content change to tables).
- **Expected:** pull_latest skips v1.0 when searching for latest. Dashboard shows strikethrough. Still accessible via pull_original and pull_version.

### UC-14: Declare an intentional override (base + overlay)
- **Preconditions:** cvff-interface/v1.5 has (ti, o) bond k=310. Alice's cvff-mxene-additions/v1.0 redefines it with k=280 for MXene chemistry.
- **Action:** Upload with `parent_ff: cvff-interface/v1.5`, declare override on (ti, o) bond scope=bonds.
- **Expected:** Manifest records `parent_ff` and `overrides`. Dashboard Conflicts page shows "cvff-mxene-additions/v1.0 overrides cvff-interface/v1.5 on (ti, o) bond — intentional". Not a warning.

---

## Edge cases

### EC-1: Atom type rename in new FF version
- **Scenario:** v1.0 has `ti4f`. v1.1 renames to `ti4fh`. Structure pinned to v1.0.
- **Expected:** v1.1 manifest declares `renames: {"ti4f": "ti4fh"}`. pull_latest composes renames, auto-applies, succeeds. Banner: "auto-renamed 1 atom type (ti4f → ti4fh)". Simulation-ready output uses v1.1's naming.

### EC-2: Atom type removed in latest
- **Scenario:** v1.2 drops `ti4f` entirely (no rename declared). Structure uses `ti4f`.
- **Expected:** pull_latest compatibility = ERROR. Fallback to v1.1 (highest compatible). Banner: "Latest v1.2 missing type 'ti4f', returning v1.1". User can still pull v1.2 explicitly (fails with clear error) or pull_original.

### EC-3: FF breaking change (units/style)
- **Scenario:** v2.0 changes nonbonded style A-B → eps-rmin. Declares `breaking: true`. Structure pinned to v1.0.
- **Expected:** pull_latest stops at v1.x (highest pre-breaking compatible version). Banner: "breaking change in v2.0, returning v1.3". pull_version(v2.0) returns WARNING status with breaking flag.

### EC-4: FF version deprecation hides from latest
- **Scenario:** v1.1 deprecated. v1.0 and v1.2 not.
- **Expected:** pull_latest walks latest → not deprecated, so returns v1.2. v1.1 still retrievable by explicit version.

### EC-5: Multiple FF families on one structure
- **Scenario:** Structure uses both a mineral FF (cvff-mxene-additions) and a solvent FF (pcff-interface). `parameterized_with: [{mxene, v1.0}, {pcff, v1.5}]`.
- **Expected:** pull_latest resolves each family independently. Returns union of tables. Compatibility check covers both. If either family has no compatible version, fallback applies per-family.

### EC-6: Duplicate version collision on upload
- **Scenario:** Alice uploads cvff-mxene@v2.0 in PR A. Bob uploads cvff-mxene@v2.0 in parallel PR B.
- **Expected:** First merged wins. Second PR's CI fails: "version v2.0 already exists for cvff-mxene". Second PR must rename (v2.0-bob) or bump (v2.1).

### EC-7: Forward reference (structure points to non-existent FF)
- **Scenario:** Structure manifest says `parameterized_with: cvff-mxene@v1.0` but no such entry.
- **Expected:** CI `validate.py` fails with: "broken reference at structures/.../manifest.json". PR blocked. Common case: FF and structure uploaded in one PR; both validated together.

### EC-8: Accidental deletion of a version directory
- **Scenario:** Someone `git rm`s `parameters/cvff-mxene/v1.0/`.
- **Expected:** CI fails on any entries referencing v1.0. PR rejected. Recovery: `git revert`. Preferred alternative: mark `deprecated: true` instead of deleting.

### EC-9: Structure uses atom types missing from its pinned FF
- **Scenario:** Structure's atoms.csv has `ti5fx` but FF@v1.0 has no such type.
- **Expected:** CI fails at upload: "atom type 'ti5fx' in structure not found in cvff-mxene@v1.0". PR blocked.

### EC-10: Two structures diverging only on per-atom charges
- **Scenario:** Same geometry, same FF pin, but charges refitted via different QM method.
- **Expected:** Both valid as separate structure entries (different `version` or different `model_name`). Not a conflict — charges are structure-level, not FF-level.

### EC-11: "What was latest when uploaded?"
- **Scenario:** User asks which FF version was latest when structure was ingested.
- **Expected:** `parameterized_with` is the original pin, which at upload time WAS latest. Combined with git commit date (when structure entry was created), this is fully reconstructable.

### EC-12: Structure locked to original
- **Scenario:** User uploads a structure that reproduces a specific paper and wants pull_latest disabled.
- **Action:** Set `lock_to_original: true` in manifest.
- **Expected:** pull_latest returns original with banner "pinned by author, pull_latest disabled". pull_version still works.

### EC-13: FF family forks (cvff-mxene splits into cvff-mxene-basal + cvff-mxene-edge)
- **Scenario:** Old structures point at `cvff-mxene-additions`. Fork creates two new families.
- **Expected:** Old structures keep pointing at cvff-mxene-additions (still exists, just not getting new versions). New structures choose a fork. Both forks live in parallel. No automatic migration.

### EC-14: Mid-PR rename in same FF bump
- **Scenario:** v1.1 renames `ti4f → ti4fh` and simultaneously removes `c1-base`.
- **Expected:** `renames` map applied first, then missing types checked. Structure using only `ti4f` → succeeds. Structure using `c1-base` → fails. Structure using both → fails on c1-base, succeeds on ti4f.

### EC-15: Conflicting overrides (two overlay bundles both override the same base bond)
- **Scenario:** cvff-mxene-additions/v1.0 overrides (ti, o) bond. cvff-ceramic-surfaces/v1.0 ALSO overrides (ti, o) bond with different value.
- **Expected:** Both declare their override. Not a library-level error — downstream users choose which overlay to compose. Dashboard Conflicts page flags it as "two independent overrides of same key — user must choose".

### EC-16: Amending provenance after publish
- **Scenario:** Author realizes DOI field was wrong. Wants to fix.
- **Expected:** Metadata-only amendments to manifest are allowed (no content change to tables). Commit message explains. Table sha256s unchanged. Discouraged but tolerated. Content-affecting changes require a new version.

### EC-17: PCFF 9-6 nonbonded / cross-terms on ingest
- **Scenario:** PCFF source file contains 9-6 nonbonded + cross-term sections that current UPM codec doesn't parse.
- **Expected:** Bundle ingested with `partial_roundtrip: true`. Raw source preserved verbatim in `raw/source.frc`. Parseable tables (atom_types, bonds, angles, torsions, OOP) populated. Non-parseable sections stored in `raw/unknown_sections.json`. Dashboard shows a "partial parse" badge; download offers raw source or parseable CSVs.

### EC-18: Hash mismatch detected by CI
- **Scenario:** Someone edits `tables/bonds.csv` directly without updating manifest sha256.
- **Expected:** CI fails: "sha256 mismatch for bonds.csv in cvff-mxene@v1.0". PR blocked. Fix: bump to new version (or revert edit).

### EC-19: Schema version bump
- **Scenario:** ARCHITECTURE.md schema goes from 0.2.0 → 0.3.0. Old entries declare schema_version: 0.2.0.
- **Expected:** Validators accept entries matching their declared schema. Migration scripts can upgrade old entries. Mixed-schema library is supported as long as loader knows both.

### EC-20: Entry-point package removed from environment
- **Scenario:** `iff-mxene-v2` uninstalled. Structures in iff-parameters that reference it.
- **Expected:** pull_latest / pull_original for those structures fails at resolution: "family cvff-mxene-v2 not discoverable". UI shows "unresolvable" badge. User advised to install the package.

### EC-21: Unicode/special characters in paths or atom types
- **Scenario:** Author name contains non-ASCII. Atom type contains `*` or whitespace.
- **Expected:** Author names: UTF-8 everywhere, round-trips cleanly. Atom types: ASCII-safe restriction enforced at upload (reject names with whitespace/special chars except `-` `_` `+`).

### EC-22: Very large structure upload (>100k atoms)
- **Scenario:** User uploads a 500k-atom system.
- **Expected:** Streamlit uploader accepts (default limit is 200 MB; configurable). Parsing is streaming where possible. Dashboard caches atoms.csv as parquet for large structures.

### EC-23: Concurrent uploads to the same family
- **Scenario:** Two users open Upload pages, both try to create v1.1 of the same family.
- **Expected:** Local-file-writes collide only at git-PR time. First PR merged wins; second fails CI (duplicate version). No in-dashboard locking needed.

### EC-24: Circular `supersedes` reference
- **Scenario:** v1.0 manifest `supersedes: "v1.1"`, v1.1 `supersedes: "v1.0"`.
- **Expected:** CI detects cycle, fails: "circular supersedes chain". Note: `supersedes` always points backward to an earlier version by convention; CI should also check version ordering.

### EC-25: Empty table in ingest
- **Scenario:** `.frc` has 0 angle entries.
- **Expected:** Bundle ingested with angles.csv present but empty (header only). Manifest records `rows: 0`. Not an error. Validation passes.

---

## Out of scope (deliberate non-support)

- **Version DAGs with multiple parents**: no merge commits of bundle versions. If two branches converge, it's a new version with manual reconciliation.
- **Automatic numeric tolerance conflict resolution**: all value disagreements flagged; humans decide, not heuristics.
- **Real-time multi-user write dashboard**: writes are file-based, gated by PR review.
- **Structure-to-type auto-parameterization**: parameterization is manual (or external); library only stores the *results* of parameterization.
- **Non-IFF force fields**: OPLS, GAFF, AMBER, etc. not prioritized. Could be added via new family but not part of initial seed.
