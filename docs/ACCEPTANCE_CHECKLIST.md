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

### Home [UC-9, UC-10]
- [ ] Four metric cards show: parameter sets (3), structures (133),
      atom types, materials
- [ ] Parameter Sets tab lists 3 entries, PCFF badged "⚠ partial roundtrip"
- [ ] Structure Database tab shows counts per class + per family

### Browse [UC-9]
- [ ] Parameters tab: select an entry, tables render with row counts
- [ ] Parameters tab → consumers section lists structures using this
      version [UC-4 visual]
- [ ] Structures tab: pick silica → atom CSV previews, raw geometry
      collapsible shows `.car` text

### Search [UC-9]
- [ ] Query atom type "ti4f" returns hits across all matching FFs
- [ ] Material filter "silica" returns silica-related bundles

### Compare [UC-8]
- [ ] Pick two different parameter versions → diff tables render
      (added / removed / changed rows)

### Download [UC-5, UC-6, UC-7]
- [ ] Parameters tab: select entry, format, tables → Download generates
      correct file
- [ ] Structure + Parameters tab:
    - Pick a structure, "latest" → resolves; shows banner if fallback
      applied [EC-2]
    - "original" → returns pinned version
    - "specific version" dropdown → per-family selection
    - Download zip bundles structure files + parameter tables +
      `pull_report.json`

### Upload [UC-2, UC-3, UC-14]
- [ ] Upload a known duplicate `.frc` → conflict preview shows "✓ duplicate"
      rows, 0 disagreements
- [ ] Modify a single bond value in the duplicate → preview shows one
      "⚠ conflict" row
- [ ] Intent selector drives which manifest fields are populated (new
      family, new version, override)
- [ ] Ingest gated on "I've reviewed" checkbox when conflicts present

### Upload Structure [UC-4]
- [ ] Drop a known-good `.car` → coverage table identifies which FF
      family covers all types → ingest succeeds
- [ ] Drop a `.car` with an unknown atom type → coverage table shows
      every family missing types, auto-suggest may be empty
- [ ] `lock_to_original` toggle visible and persisted [EC-12]

### Conflicts [UC-14]
- [ ] Page loads; shows cross-family CVFF↔PCFF shared-type disagreements
      (mass_amu, a few bonds, torsions) from live library
- [ ] Scope filter works; key substring filter works
- [ ] CSV download contains all rows

### Coverage
- [ ] Grid shows materials × families with `P:N@vX.Y / S:N` cells
- [ ] Gaps list non-empty for missing cells
- [ ] Per-class bar chart renders

## Validator / CI

- [ ] `scripts/validate.py` emits warnings (not errors) for V-9
      cross-family conflicts in the live library
- [ ] `scripts/check_immutability.py` runs without error on the current
      branch
- [ ] `.github/workflows/ci.yml` lints, tests, and validates on push

## Documentation

- [x] `docs/ARCHITECTURE.md` is the spec of record
- [x] `docs/USE_CASES.md` enumerates 14 UCs + 25 ECs
- [x] `docs/VALIDATION_PLAN.md` maps each case to a test
- [x] `docs/ACCEPTANCE_CHECKLIST.md` (this file) exists
- [ ] `README.md` updated for v0.2 (new layout, pull ops, upload flow)

## Cutover

- [ ] Acceptance checklist walked end-to-end on a fresh clone
- [ ] Merge `v0.2-rebuild` → `main`
- [ ] Tag `v0.2.0`
- [ ] Streamlit Cloud auto-deploys; verify live URL loads
- [ ] Announce to group

---

Any box unchecked means the rebuild isn't ready. File bugs inline in the
PR for any failures; re-run the checklist after fixes.
