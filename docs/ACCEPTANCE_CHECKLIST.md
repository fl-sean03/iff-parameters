# Acceptance Checklist for v0.2 Cutover

Walk this list before merging `v0.2-rebuild` → `main`. Each box maps back
to a specific UC or EC from `USE_CASES.md` (noted in brackets). Automated
tests cover most of this; this list is the human smoke check.

## Environment

- [x] `pip install -e .[dev]` installs cleanly on Python 3.10–3.13
- [x] `python scripts/validate.py` exits 0 against the live library
- [x] Full test suite green: `pytest -q` → 78 passed, 2 skipped (USM
      legacy tests skip when USM is not available)
- [x] Ruff clean: `ruff check src/ tests/ scripts/ dashboard/`

## Seeded library

- [x] `data/parameters/` contains `cvff-interface/v1.5`,
      `pcff-interface/v1.5`, `charmm27-interface/v1.5` [UC-1, S-1]
- [x] PCFF entry manifest has `partial_roundtrip: true` and preserves
      raw source [EC-17, S-2]
- [x] 133 structures under `data/structures/` across 7 material classes
      [S-3]
- [x] Every structure's `parameterized_with` resolves to a real entry
      [S-4]
- [x] Every structure's atom types resolve against its pinned FF [S-5]
- [x] All sha256s match on `validate_hashes=True` [S-6]
- [x] Seed scripts idempotent (byte-identical output when re-run) [S-7]

## Dashboard — walk manually on local run

```
streamlit run dashboard/app.py
```

Every item below is backed by an AppTest in `tests/ui/test_dashboard_acceptance.py`
or an integration test — the suite (107 passed) automates these checks.

### Home [UC-9, UC-10]
- [x] Four metric cards show: parameter sets (3), structures (133),
      atom types, materials
- [x] Parameter Sets tab lists 3 entries, PCFF badged "⚠ partial roundtrip"
- [x] Structure Database tab shows counts per class + per family

### Browse [UC-9]
- [x] Parameters tab: select an entry, tables render with row counts
- [x] Parameters tab → consumers section lists structures using this
      version [UC-4 visual]
- [x] Structures tab: pick silica → atom CSV previews, raw geometry
      collapsible shows `.car` text

### Search [UC-9]
- [x] Page loads; cross-family atom-type search works

### Compare [UC-8]
- [x] Pick two different parameter versions → diff tables render
      (added / removed / changed rows)

### Download [UC-5, UC-6, UC-7]
- [x] Parameters tab: select entry, format, tables → Download generates
      correct file
- [x] Structure + Parameters tab:
    - Pick a structure, "latest" → resolves (no ERROR status)
    - "original" → returns pinned version
    - "specific version" per-family dropdowns wired
    - Zip bundles structure files + parameter tables + `pull_report.json`

### Upload [UC-2, UC-3, UC-14]
- [x] Conflict-preview logic (detect_collisions) unit-tested in
      `tests/test_conflicts.py`: harmless duplicates vs. real disagreements
      distinguished correctly.
- [x] Intent selector radio wired; override path populates the `overrides`
      field on ingest (Upload page lines 187-202).
- [x] Ingest gated on "I've reviewed" checkbox when conflicts present.

### Upload Structure [UC-4]
- [x] CAR parser (iff_parameters.car_parser) unit-tested against
      tricky INTERFACE_FF_1_5 files (ca++, 3-char mol_label).
- [x] Coverage table renders per-family missing-type counts.
- [x] `lock_to_original` toggle present and forwarded to save_structure.

### Conflicts [UC-14]
- [x] Page loads; shows cross-family CVFF↔PCFF shared-type disagreements
      (live library has 10 V-9 collisions).
- [x] Scope filter multiselect works.
- [x] CSV download wired.

### Coverage
- [x] Grid shows materials × families with `P:N@vX.Y / S:N` cells.
- [x] Gaps list renders.
- [x] Per-class bar chart renders.

## Validator / CI

- [x] `scripts/validate.py` emits warnings (not errors) for V-9
      cross-family conflicts in the live library (10 warnings, 0 errors).
- [x] `scripts/check_immutability.py` runs without error on the current
      branch.
- [x] `.github/workflows/ci.yml` lints, tests, and validates on push,
      matrix-tested across Python 3.10–3.13.

## Documentation

- [x] `docs/ARCHITECTURE.md` is the spec of record
- [x] `docs/USE_CASES.md` enumerates 14 UCs + 25 ECs
- [x] `docs/VALIDATION_PLAN.md` maps each case to a test
- [x] `docs/ACCEPTANCE_CHECKLIST.md` (this file) exists
- [ ] `README.md` updated for v0.2 (new layout, pull ops, upload flow)

## Cutover

- [x] Acceptance checklist walked end-to-end (AppTest + integration suite)
- [ ] Merge `v0.2-rebuild` → `main`
- [ ] Tag `v0.2.0`
- [ ] Streamlit Cloud auto-deploys; verify live URL loads
- [ ] Announce to group

---

Any box unchecked means the rebuild isn't ready. File bugs inline in the
PR for any failures; re-run the checklist after fixes.
