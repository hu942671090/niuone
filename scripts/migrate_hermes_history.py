#!/usr/bin/env python3
"""Merge Hermes dashboard history into the NiuOne runtime.

The migration is additive:
- copy missing cron output/state files without overwriting local files
- insert missing rows from Hermes push_history.db into NiuOne push_history.db
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL_DATA_DIR = Path(os.environ.get("NIUONE_LOCAL_DATA_DIR") or ROOT / ".local-data").expanduser()
DEFAULT_DASHBOARD_HOME = DEFAULT_LOCAL_DATA_DIR / "runtime"
TABLES = ("dashboard_messages",)


def is_suppressed_cron_output(path: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    try:
        raw = path.read_text(errors="replace")
    except OSError:
        return False
    text = raw.lower()
    return (
        "**status:** script failed" in text
        or "script timed out after" in text
        or "script not found:" in text
    )


def copy_missing_tree(src: Path, dst: Path, *, dry_run: bool = False) -> int:
    if not src.exists():
        return 0
    copied = 0
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        if is_suppressed_cron_output(path):
            continue
        rel = path.relative_to(src)
        target = dst / rel
        if target.exists():
            continue
        copied += 1
        if dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return copied


def table_columns(con: sqlite3.Connection, table: str, schema: str | None = None) -> list[str]:
    if schema:
        rows = con.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    else:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return [str(row[1]) for row in rows]


def merge_push_history(src_db: Path, dst_db: Path, *, dry_run: bool = False, backup: bool = True) -> int:
    if not src_db.exists():
        return 0
    dst_db.parent.mkdir(parents=True, exist_ok=True)
    if not dst_db.exists():
        if dry_run:
            return -1
        shutil.copy2(src_db, dst_db)
        return -1

    if dry_run:
        with tempfile.TemporaryDirectory(prefix="niuone-history-merge-") as tmp:
            tmp_db = Path(tmp) / dst_db.name
            shutil.copy2(dst_db, tmp_db)
            return merge_push_history(src_db, tmp_db, dry_run=False, backup=False)

    if backup:
        backup_dir = dst_db.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(dst_db, backup_dir / f"{dst_db.name}.before-hermes-history-{stamp}")

    src_uri = "file:" + str(src_db) + "?mode=ro&immutable=1"
    con = sqlite3.connect(dst_db)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("ATTACH DATABASE ? AS src", (src_uri,))
        total_inserted = 0
        for table in TABLES:
            dst_cols = table_columns(con, table)
            src_cols = table_columns(con, table, schema="src")
            cols = [col for col in dst_cols if col in src_cols]
            if "id" not in cols:
                continue
            quoted = ", ".join(f'"{col}"' for col in cols)
            selected = ", ".join(f's."{col}"' for col in cols)
            insert_sql = (
                f"INSERT OR IGNORE INTO {table} ({quoted}) "
                f"SELECT {selected} FROM src.{table} s"
            )
            before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            con.execute(insert_sql)
            con.commit()
            after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            total_inserted += int(after - before)
        return total_inserted
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Hermes dashboard history into NiuOne runtime")
    parser.add_argument("--hermes-home", default=str(Path.home() / ".hermes"))
    parser.add_argument("--dashboard-home", default=os.environ.get("DASHBOARD_HOME", str(DEFAULT_DASHBOARD_HOME)))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    hermes_home = Path(args.hermes_home).expanduser()
    dashboard_home = Path(args.dashboard_home).expanduser()

    output_copied = copy_missing_tree(hermes_home / "cron" / "output", dashboard_home / "cron" / "output", dry_run=args.dry_run)
    state_copied = copy_missing_tree(hermes_home / "cron" / "state", dashboard_home / "cron" / "state", dry_run=args.dry_run)
    db_inserted = merge_push_history(hermes_home / "push_history.db", dashboard_home / "push_history.db", dry_run=args.dry_run)

    print(f"hermes_home={hermes_home}")
    print(f"dashboard_home={dashboard_home}")
    print(f"cron_output_files_copied={output_copied}")
    print(f"cron_state_files_copied={state_copied}")
    if db_inserted == -1:
        print("push_history_db=copied_whole_db")
    else:
        print(f"push_history_rows_inserted={db_inserted}")
    if args.dry_run:
        print("dry_run=true")


if __name__ == "__main__":
    main()
