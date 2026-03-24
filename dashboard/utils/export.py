"""Export helpers for the dashboard download page."""
from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd


def export_tables_csv_zip(tables: dict[str, pd.DataFrame]) -> bytes:
    """Export selected tables as a ZIP of CSVs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, df in sorted(tables.items()):
            csv_data = df.to_csv(index=False).encode("utf-8")
            zf.writestr(f"{name}.csv", csv_data)
    return buf.getvalue()


def export_as_frc(tables: dict[str, Any]) -> bytes:
    """Export tables as a .frc file."""
    from upm.codecs.msi_frc import write_frc

    with tempfile.NamedTemporaryFile(suffix=".frc", delete=False) as f:
        write_frc(f.name, tables=tables, mode="full")
        return Path(f.name).read_bytes()


def export_as_prm(tables: dict[str, Any]) -> bytes:
    """Export tables as a .prm file."""
    from upm.codecs.charmm_prm import write_prm

    with tempfile.NamedTemporaryFile(suffix=".prm", delete=False) as f:
        write_prm(f.name, tables=tables)
        return Path(f.name).read_bytes()
