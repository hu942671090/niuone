#!/usr/bin/env python3
"""Compatibility entrypoint for the A-share close report."""
import sys
from pathlib import Path
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))
from _compat import exec_relocated
exec_relocated(globals(), "reports/a_share/close_summary.py")
