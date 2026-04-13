# Scaffold a downstream overlay package

Use this recipe when a project in the group wants to publish its own
parameter additions (e.g., MXene-specific tweaks, ceramic surface
variants) as a separate pip-installable package that plugs into the
iff-parameters registry via UPM entry points.

## Layout

```
iff-<your-project>/
├── pyproject.toml
├── src/
│   └── iff_<your_project>/          # note: underscore, not dash
│       ├── __init__.py
│       └── data/
│           └── parameters/
│               └── cvff-<project>-additions/
│                   └── v1.0/
│                       ├── manifest.json
│                       ├── tables/
│                       └── raw/
└── README.md
```

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "iff-<your-project>"
version = "0.1.0"
description = "IFF parameter overlay for <materials>"
requires-python = ">=3.10"
dependencies = [
  "upm >= 2.1",
  "iff-parameters",              # for the base FF families you extend
]

[project.entry-points."upm.data_packages"]
<your_project> = "iff_<your_project>:get_data_dir"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

## src/iff_<your_project>/__init__.py

```python
"""IFF parameter overlay for <your project>."""
from pathlib import Path

__version__ = "0.1.0"

def get_data_dir() -> Path:
    """Entry-point callable discovered by upm.registry."""
    return Path(__file__).parent / "data"
```

## Writing an overlay manifest

Your new parameter entry declares `parent_ff` and explicit overrides:

```json
{
  "schema_version": "upm-2.1",
  "name": "cvff-mxene-additions",
  "version": "v1.0",
  "type": "parameters",
  "parent_ff": "cvff-interface/v1.5",
  "overrides": [
    {"target": "cvff-interface/v1.5", "scope": "bonds",
     "reason": "DFT benchmark refinement for Ti-O"}
  ],
  "provenance": {
    "author": "Your Name",
    "lab": "Heinz Lab, CU Boulder",
    "materials": ["MXene", "Ti3C2"],
    "source_file": "cvff_mxene_v1.frc",
    "source_sha256": "…"
  },
  "units": {"length": "angstrom", "energy": "kcal/mol",
            "mass": "amu", "angle": "degree"},
  "nonbonded": {"style": "A-B", "form": "12-6", "mixing": "geometric"},
  "tables": {
    "atom_types": {"path": "tables/atom_types.csv", ...},
    "bonds": {"path": "tables/bonds.csv", ...}
  },
  "sources": [
    {"path": "raw/source.frc", "sha256": "…"}
  ]
}
```

Create the manifest programmatically:

```python
from upm.bundle.io import save_package

save_package(
    Path("src/iff_mxene/data/parameters/cvff-mxene-additions/v1.0"),
    name="cvff-mxene-additions",
    version="v1.0",
    tables=my_tables,
    source_text=my_frc_text,
    source_format="frc",
    parent_ff="cvff-interface/v1.5",
    overrides=[{"target": "cvff-interface/v1.5", "scope": "bonds",
                "reason": "DFT"}],
    provenance={
        "author": "Your Name",
        "source_file": "cvff_mxene_v1.frc",
        "source_sha256": hashlib.sha256(my_frc_text.encode()).hexdigest(),
        "materials": ["MXene", "Ti3C2"],
    },
)
```

## Installing alongside iff-parameters

```bash
pip install iff-parameters
pip install -e iff-<your-project>/
```

UPM's `discover_packages()` now returns entries from both. The
iff-parameters dashboard (if you run it locally pointing at a
virtualenv with your overlay installed) will surface your overlay's
entries in Browse / Search / Conflicts / Coverage automatically.

## Structures too

If your project also ships pre-parameterized structures, put them under
`data/structures/<material-class>/<model>/<version>/` with
`parameterized_with: [{"name": "cvff-mxene-additions", "version": "v1.0"}]`
in each structure manifest. Same overlay package, two entry kinds.

## Conventions

- **Version strings** stay linear per family (`v1.0 → v1.1 → v2.0`).
  Major bump only when you declare `breaking: true`.
- **Never overwrite** a published version. New fixes → new version.
- **Declare renames** when you change atom type names so `pull_latest`
  auto-migrates pinned structures.
- **Declare overrides** so the parent library's conflict page can show
  the disagreement as intentional.

## Testing your overlay

```bash
cd iff-<your-project>
pytest                          # your unit tests
python -c "from upm.registry.discovery import discover_packages; \
           print([p.name for p in discover_packages()])"
# ['iff', '<your_project>', ...]
```

Lint with the same ruff rules as iff-parameters. Bundle validation:

```bash
python -c "from upm.bundle.io import load_package; \
           load_package('src/iff_<your_project>/data/parameters/.../v1.0', \
                        validate_hashes=True)"
```
