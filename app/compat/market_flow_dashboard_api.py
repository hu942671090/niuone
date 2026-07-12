#!/usr/bin/env python3
"""Compatibility module for the retired market-flow API."""
import sys
from pathlib import Path
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))
from _compat import exec_relocated
exec_relocated(globals(), "dashboard/apis/market_flow_facade.py")
