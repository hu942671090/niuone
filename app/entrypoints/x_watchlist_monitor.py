#!/usr/bin/env python3
import sys
from pathlib import Path
_ENTRYPOINT_DIR = Path(__file__).resolve().parent
if str(_ENTRYPOINT_DIR) not in sys.path:
    sys.path.insert(0, str(_ENTRYPOINT_DIR))
from _bootstrap import run
run(globals(), "monitoring/x/monitor_service.py", "x_watchlist_monitor.py")
