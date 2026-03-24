# Contributing to iff-parameters

## How to Add New Force Field Parameters

### Step 1: Prepare Your File

Place your `.frc` or `.prm` file somewhere accessible. It can come from:
- Materials Studio export
- Optimization pipeline output
- Another lab member's shared folder
- Dropbox/Google Drive

### Step 2: Run the Ingest Script

```bash
cd /path/to/iff-parameters

python scripts/ingest.py \
    --path /path/to/my_forcefield.frc \
    --name my-ff-name \
    --version v1.0 \
    --author "Your Name" \
    --materials "Au,SiO2,water" \
    --notes "Custom params for solvation project"
```

The script will:
1. Parse the file (auto-detects `.frc` vs `.prm`)
2. Show a **similarity report** against existing bundles
3. Save a versioned bundle with SHA256 provenance
4. Verify the roundtrip (parse → bundle → reload)

**If the similarity report shows >90% overlap** with an existing bundle, consider making it a version bump instead of a new bundle:
```bash
python scripts/ingest.py \
    --path /path/to/updated_ff.frc \
    --name existing-bundle-name \
    --version v2.0 \
    --notes "Updated hydroxyl charges for paper revision"
```

### Step 3: Create a Branch and PR

```bash
git checkout -b add-my-ff-params
git add src/iff_parameters/data/my-ff-name/
git commit -m "feat: add my-ff-name parameters for solvation project"
git push origin add-my-ff-params
```

Then open a Pull Request on GitHub. CI will automatically:
- Run all tests
- Validate bundle integrity (SHA256 hashes, provenance)
- Check for lint issues

### Step 4: Review

A lab member with write access reviews the PR:
- Are the materials and provenance metadata accurate?
- Is this a new bundle or should it be a version bump of an existing one?
- Does the validation pass?

Once approved and merged, the parameters are canonical and discoverable by everyone.

---

## Updating Existing Parameters

When you optimize or correct parameters in an existing bundle:

```bash
# Ingest as a new version of the same bundle
python scripts/ingest.py \
    --path optimized_alumina.frc \
    --name cvff-iff-metal-oxides-v2 \
    --version v2.0 \
    --author "Your Name" \
    --notes "Optimized Al2O3 hydroxyl charges — RMSE improved 15%"
```

This creates `v2.0` alongside `v1.0`. Both versions are preserved. Use `upm diff` to see what changed:
```bash
# From Python
from upm.registry.diff import diff_tables
from upm.bundle.io import load_package
from iff_parameters import get_data_dir

old = load_package(get_data_dir() / "cvff-iff-metal-oxides-v2" / "v1.0")
new = load_package(get_data_dir() / "cvff-iff-metal-oxides-v2" / "v2.0")
diff = diff_tables(old.tables, new.tables)
print(diff.summary())
```

---

## Batch Ingestion

To scan a directory and ingest all `.frc`/`.prm` files:

```bash
# Preview (dry run)
python scripts/batch_ingest.py --scan-dir ~/Dropbox/forcefields/ --dry-run

# Ingest (skips duplicates by SHA256)
python scripts/batch_ingest.py --scan-dir ~/Dropbox/forcefields/
```

---

## Validation

Verify all bundles are intact:
```bash
python scripts/validate.py
```

---

## What NOT to Commit

- Don't commit files to `canonical_sources/` (gitignored staging area)
- Don't modify `manifest.json` by hand — use the ingest script
- Don't modify CSV table files — they're auto-generated from source files
