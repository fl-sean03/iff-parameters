"""Add dashboard/ to sys.path so pages can import `utils.data`."""
import sys
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent.parent / "dashboard"
if str(DASHBOARD) not in sys.path:
    sys.path.insert(0, str(DASHBOARD))
