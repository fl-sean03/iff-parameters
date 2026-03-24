# iff-parameters — INTERFACE Force Field Data Package

Curated, versioned parameter bundles for the [INTERFACE Force Field (IFF)](https://github.com/hendrikheinz/INTERFACE-force-field-and-surface-models) by Hendrik Heinz, compatible with [UPM v2.0](https://github.com/fl-sean03/upm).

## Install

```bash
pip install git+https://github.com/fl-sean03/iff-parameters.git
```

UPM must also be installed:
```bash
pip install git+https://github.com/fl-sean03/upm.git
```

## Included Parameter Sets

| Bundle | Format | Materials | Atom Types |
|--------|--------|-----------|------------|
| `cvff-interface-v1-5` | CVFF (.frc) | Ag, Al, Au, Cu, Ni, Pb, Pd, Pt, silica, clays | 180 |
| `cvff-iff-metal-oxides-v2` | CVFF (.frc) | Al₂O₃, SiO₂, clays | 280 |
| `cvff-iff-ils` | CVFF (.frc) | Ionic liquids, CO₂, MOFs | 224 |
| `iff-charmm36-metal-alumina-v8` | CHARMM (.prm) | FCC metals, Al₂O₃ | 239 |

## Usage

### List available parameters
```python
from iff_parameters import list_available, search_by_material

# List all
for entry in list_available():
    print(f"{entry['name']}@{entry['version']} — {entry['materials']}")

# Search by material
results = search_by_material("Au")
```

### With UPM registry
```python
from upm.registry import discover_packages, PackageIndex

packages = discover_packages()  # Auto-discovers iff-parameters
index = PackageIndex(packages)
results = index.search_atom_type("Au")
```

### Diff two parameter sets
```python
from upm.registry import diff_tables
from upm.bundle.io import load_package
from pathlib import Path
from iff_parameters import get_data_dir

pkg1 = load_package(get_data_dir() / "cvff-interface-v1-5" / "v1.0")
pkg2 = load_package(get_data_dir() / "cvff-iff-metal-oxides-v2" / "v1.0")
diff = diff_tables(pkg1.tables, pkg2.tables)
print(diff.summary())
```

## Ingesting New Files

### Single file
```bash
python scripts/ingest.py \
    --path my_forcefield.frc \
    --name my-ff-name \
    --version v1.0 \
    --author "Your Name" \
    --materials "Au,Cu,SiO2"
```

### Batch from directory
```bash
python scripts/batch_ingest.py --scan-dir ~/Dropbox/forcefields/
python scripts/batch_ingest.py --scan-dir ~/Dropbox/forcefields/ --dry-run  # preview
```

### Validate all bundles
```bash
python scripts/validate.py
```

## Provenance

Each bundle tracks:
- **author**: Who created/curated this parameter set
- **source_file**: Original filename
- **source_sha256**: Integrity hash of the source file
- **publication_doi**: Associated publication
- **parent_ff**: Base force field this extends (e.g., `cvff_interface_v1_5`)
- **materials**: What materials are covered
- **ingested_utc**: When this bundle was created

## Architecture

This package integrates with UPM v2.0 via Python entry points:
- Entry point group: `upm.data_packages`
- Callable: `iff_parameters:get_data_dir` returns `Path` to bundle data
- UPM's `discover_packages()` auto-discovers installed bundles
- Each bundle follows UPM's standard format: `manifest.json` + `tables/*.csv` + `raw/source.frc`
