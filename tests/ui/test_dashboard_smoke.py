"""Dashboard smoke tests using Streamlit's AppTest harness.

These are lightweight checks that each page imports cleanly and produces
*some* output without raising exceptions. Exhaustive interaction testing
is covered by Playwright/manual acceptance.
"""
from __future__ import annotations

from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1", reason="Streamlit AppTest unavailable")
from streamlit.testing.v1 import AppTest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD = REPO_ROOT / "dashboard"


@pytest.mark.parametrize("page", [
    "app.py",
    "pages/1_Search.py",
    "pages/2_Browse.py",
    "pages/3_Compare.py",
    "pages/4_Download.py",
    "pages/5_Upload.py",
    "pages/6_Upload_Structure.py",
    "pages/7_Conflicts.py",
    "pages/8_Coverage.py",
])
def test_page_loads(page):
    """Every page must initialize without raising."""
    at = AppTest.from_file(str(DASHBOARD / page), default_timeout=15)
    at.run()
    # Any exception surfaces here. We don't assert specific content because
    # pages render conditionally based on library state.
    assert not at.exception, (
        f"{page} raised during render:\n" + "\n".join(
            repr(e) for e in at.exception
        )
    )
