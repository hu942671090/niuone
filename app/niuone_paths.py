"""Shared local path defaults for NiuOne.

Runtime data lives in an ignored .local-data directory by default so a repository upload
does not accidentally commit databases, tokens, logs, or generated reports.
"""
from __future__ import annotations

import os
from pathlib import Path


def get_local_data_dir(root: Path) -> Path:
    return Path(os.environ.get("NIUONE_LOCAL_DATA_DIR") or root / ".local-data").expanduser()


def get_dashboard_home(root: Path) -> Path:
    return Path(os.environ.get("DASHBOARD_HOME") or get_local_data_dir(root) / "runtime").expanduser()


def get_dashboard_env_file(root: Path) -> Path:
    if os.environ.get("DASHBOARD_ENV_FILE"):
        return Path(os.environ["DASHBOARD_ENV_FILE"]).expanduser()
    project_env = root / "dashboard.env"
    if project_env.exists():
        return project_env
    return get_local_data_dir(root) / "dashboard.env"
