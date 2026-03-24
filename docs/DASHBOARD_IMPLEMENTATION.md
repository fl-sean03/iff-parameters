# IFF Parameters Dashboard — Implementation Plan

## Overview

Streamlit web dashboard for browsing, searching, comparing, and downloading
INTERFACE Force Field parameters. Hosted on Streamlit Community Cloud (free).

**Repo:** `fl-sean03/iff-parameters` (dashboard lives alongside data package)
**Entry point:** `streamlit run dashboard/app.py`
**Deployment:** Streamlit Community Cloud → auto-deploy on push

## Directory Structure

```
dashboard/
├── app.py                    # Main entry point + Home page
├── pages/
│   ├── 1_Search.py          # Atom type / element / material search
│   ├── 2_Browse.py          # Detailed table browser per bundle
│   ├── 3_Compare.py         # Side-by-side bundle diff
│   └── 4_Download.py        # Multi-format export
├── utils/
│   ├── __init__.py
│   ├── data.py              # Bundle loading + caching
│   ├── search.py            # Search operations
│   └── export.py            # FRC/PRM/CSV export helpers
└── .streamlit/
    └── config.toml          # Theme + settings
```

## Implementation Phases

### Phase 1: Core + Home page (app.py)
- Set up dashboard/ directory
- app.py with page_config, sidebar, metrics, bundle overview table
- utils/data.py with cached bundle loading
- .streamlit/config.toml

### Phase 2: Search page
- Atom type search with text input + filtered results table
- Material search with multiselect
- Cross-bundle results display

### Phase 3: Browse page
- Bundle selector dropdown
- Tabbed view: Atom Types | Bonds | Angles | Torsions | OOP | Metadata
- Per-table filtering and CSV export buttons

### Phase 4: Compare page
- Two bundle selectors
- Diff summary metrics (added/removed/changed)
- Side-by-side parameter table

### Phase 5: Download page
- Format selection (FRC/PRM/CSV)
- Table selection checkboxes
- st.download_button with generated file

### Phase 6: Polish + deploy
- requirements.txt
- Test locally
- Push to GitHub
- Deploy to Streamlit Community Cloud

## Dependencies

```
streamlit>=1.35.0
pandas>=2.1
numpy>=1.24
# iff-parameters and upm installed from GitHub
```

## Key APIs Used

```python
# Data loading
from iff_parameters import list_available, search_by_material, get_data_dir
from upm.bundle.io import load_package
from upm.registry.discovery import discover_local_packages
from upm.registry.index import PackageIndex
from upm.registry.diff import diff_tables

# Export
from upm.codecs.msi_frc import write_frc
from upm.codecs.charmm_prm import write_prm
```
