#!/usr/bin/env python3
"""SQLite storage for NiuOne dashboard push history.

This module is intentionally standalone so scripts, local workers, and small
dashboards can share the same durable history store without importing the
dashboard service.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

from niuone_paths import get_dashboard_home

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_HOME = get_dashboard_home(PROJECT_ROOT)
DB_PATH = Path(os.environ.get("DASHBOARD_PUSH_HISTORY_DB") or str(DASHBOARD_HOME / "push_history.db"))
SCHEMA_VERSION = 1


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    init_db(con)
    return con


def init_db(con: sqlite3.Connection) -> None:
    # FTS triggers from the first DB draft made repeated upserts fragile on some
    # markdown/emoji payloads. The dashboard currently filters client-side, and
    # server-side search below uses indexed rows + LIKE, so drop those triggers
    # to keep ingestion reliable. A future FTS migration can rebuild the index
    # out-of-band without blocking delivery/history writes.
    con.executescript(
        """
        DROP TRIGGER IF EXISTS dashboard_messages_ai;
        DROP TRIGGER IF EXISTS dashboard_messages_ad;
        DROP TRIGGER IF EXISTS dashboard_messages_au;
        """
    )
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dashboard_messages (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            time_text TEXT,
            category TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT,
            source_label TEXT,
            platform TEXT,
            platform_label TEXT,
            chat TEXT,
            chat_label TEXT,
            external_id TEXT,
            title TEXT,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            chars INTEGER,
            matched INTEGER NOT NULL DEFAULT 0,
            kind TEXT,
            delivery_json TEXT,
            metadata_json TEXT,
            raw_path TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_source_external
            ON dashboard_messages(source_type, source_id, external_id)
            WHERE external_id IS NOT NULL AND external_id != '';

        CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_raw_path
            ON dashboard_messages(raw_path)
            WHERE raw_path IS NOT NULL AND raw_path != '';

        CREATE INDEX IF NOT EXISTS idx_dashboard_category_time
            ON dashboard_messages(category, timestamp DESC);

        CREATE INDEX IF NOT EXISTS idx_dashboard_time
            ON dashboard_messages(timestamp DESC);

        CREATE INDEX IF NOT EXISTS idx_dashboard_platform_chat
            ON dashboard_messages(platform, chat);
        """
    )
    con.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    con.commit()


def stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(p or "") for p in parts)
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:32]


def content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8", "replace")).hexdigest()


def dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def upsert_message(con: sqlite3.Connection, message: dict[str, Any]) -> str:
    """Insert or update one dashboard message.

    Required: timestamp, category, source_type, content.
    Recommended for dedupe: external_id or raw_path. If id is absent, it is
    derived from source/external/content fields.
    """
    now = time.time()
    timestamp = float(message.get("timestamp") or now)
    content = str(message.get("content") or "")
    source_type = str(message.get("source_type") or message.get("source") or "unknown")
    source_id = str(message.get("source_id") or "")
    external_id = str(message.get("external_id") or "")
    raw_path = str(message.get("raw_path") or "")
    base_key_parts = [source_type, source_id, external_id, raw_path]
    if external_id or raw_path:
        msg_id = str(message.get("id") or stable_id(*base_key_parts))
    else:
        msg_id = str(message.get("id") or stable_id(source_type, source_id, timestamp, content_hash(content)))
    if external_id:
        con.execute(
            """
            DELETE FROM dashboard_messages
            WHERE source_type = ? AND source_id = ? AND external_id = ? AND id != ?
            """,
            (source_type, source_id, external_id, msg_id),
        )
    if raw_path:
        con.execute(
            """
            DELETE FROM dashboard_messages
            WHERE raw_path = ? AND id != ?
            """,
            (raw_path, msg_id),
        )
    params = {
        "id": msg_id,
        "timestamp": timestamp,
        "time_text": message.get("time_text") or message.get("time") or "",
        "category": str(message.get("category") or "other"),
        "source_type": source_type,
        "source_id": source_id,
        "source_label": message.get("source_label") or "",
        "platform": message.get("platform") or "",
        "platform_label": message.get("platform_label") or "",
        "chat": message.get("chat") or "",
        "chat_label": message.get("chat_label") or "",
        "external_id": external_id,
        "title": message.get("title") or "",
        "content": content,
        "content_hash": content_hash(content),
        "chars": int(message.get("chars") if message.get("chars") is not None else len(content)),
        "matched": 1 if message.get("matched") else 0,
        "kind": message.get("kind") or "",
        "delivery_json": dumps(message.get("delivery")),
        "metadata_json": dumps(message.get("metadata")),
        "raw_path": raw_path,
        "created_at": float(message.get("created_at") or now),
        "updated_at": now,
    }
    con.execute(
        """
        INSERT INTO dashboard_messages (
            id, timestamp, time_text, category, source_type, source_id, source_label,
            platform, platform_label, chat, chat_label, external_id, title, content,
            content_hash, chars, matched, kind, delivery_json, metadata_json, raw_path,
            created_at, updated_at
        ) VALUES (
            :id, :timestamp, :time_text, :category, :source_type, :source_id, :source_label,
            :platform, :platform_label, :chat, :chat_label, :external_id, :title, :content,
            :content_hash, :chars, :matched, :kind, :delivery_json, :metadata_json, :raw_path,
            :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            timestamp=excluded.timestamp,
            time_text=excluded.time_text,
            category=excluded.category,
            source_type=excluded.source_type,
            source_id=excluded.source_id,
            source_label=excluded.source_label,
            platform=excluded.platform,
            platform_label=excluded.platform_label,
            chat=excluded.chat,
            chat_label=excluded.chat_label,
            external_id=excluded.external_id,
            title=excluded.title,
            content=excluded.content,
            content_hash=excluded.content_hash,
            chars=excluded.chars,
            matched=excluded.matched,
            kind=excluded.kind,
            delivery_json=excluded.delivery_json,
            metadata_json=excluded.metadata_json,
            raw_path=excluded.raw_path,
            updated_at=excluded.updated_at
        """,
        params,
    )
    return msg_id


def upsert_many(messages: Iterable[dict[str, Any]]) -> int:
    con = connect()
    count = 0
    try:
        with con:
            for message in messages:
                upsert_message(con, message)
                count += 1
    finally:
        con.close()
    return count


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["matched"] = bool(item.get("matched"))
    for key in ("delivery_json", "metadata_json"):
        value = item.pop(key, None)
        out_key = key.replace("_json", "")
        if value:
            try:
                item[out_key] = json.loads(value)
            except Exception:
                item[out_key] = None
        else:
            item[out_key] = None
    # Backward-compatible names used by the existing dashboard frontend.
    item["time"] = item.get("time_text") or ""
    item["session_id"] = item.get("source_id") or ""
    return item


def query_messages(
    *,
    category: str | None = None,
    chat: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    con = connect()
    try:
        where = []
        params: list[Any] = []
        if category:
            where.append("m.category = ?")
            params.append(category)
        if chat:
            where.append("m.chat = ?")
            params.append(chat)
        if q:
            like = f"%{q}%"
            where.append("(m.title LIKE ? OR m.content LIKE ? OR m.source_label LIKE ? OR m.chat_label LIKE ? OR m.source_id LIKE ?)")
            params.extend([like, like, like, like, like])
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        from_sql = "dashboard_messages m"
        rows = con.execute(
            f"""
            SELECT m.* FROM {from_sql} {where_sql}
            ORDER BY
              m.timestamp DESC,
              CASE WHEN m.kind = 'cron_output' THEN 0 ELSE 1 END,
              length(m.content) DESC,
              m.id DESC
            """,
            params,
        ).fetchall()
        def _dedupe_key(row: sqlite3.Row) -> str:
            content = str(row["content"] or "")
            normalized = " ".join(content.split())[:220]
            if row["category"] == "us_ratings" and "买入评级" in content:
                return f"us_ratings:{normalized}"
            if row["category"] == "x_monitor" and row["external_id"]:
                return f"x_monitor:{row['external_id']}"
            return f"{row['id']}"

        def _x_metadata_priority(row: sqlite3.Row) -> int:
            if row["category"] != "x_monitor":
                return 0
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except Exception:
                metadata = {}
            post = metadata.get("post") if isinstance(metadata, dict) else None
            if not isinstance(post, dict):
                return 3
            media_fields = ("media", "reply_to_media", "quoted_media")
            if any(post.get(field) for field in media_fields):
                return 0
            return 1

        def _priority(row: sqlite3.Row) -> tuple[int, int, int]:
            kind_priority = 0 if row["kind"] == "cron_output" else 1
            return (_x_metadata_priority(row), kind_priority, -len(str(row["content"] or "")))

        deduped: dict[str, sqlite3.Row] = {}
        for row in rows:
            key = _dedupe_key(row)
            current = deduped.get(key)
            if current is None or _priority(row) < _priority(current):
                deduped[key] = row
        rows = list(deduped.values())
        matched_total = len(rows)
        start = max(int(offset or 0), 0)
        if limit is not None:
            rows = rows[start:start + max(int(limit), 1)]
        elif start:
            rows = rows[start:]

        category_rows = con.execute(
            """
            SELECT m.* FROM dashboard_messages m
            ORDER BY
              m.timestamp DESC,
              CASE WHEN m.kind = 'cron_output' THEN 0 ELSE 1 END,
              length(m.content) DESC,
              m.id DESC
            """
        ).fetchall()
        categories: dict[str, int] = {}
        seen_category_keys: set[str] = set()
        for row in category_rows:
            key = _dedupe_key(row)
            if key in seen_category_keys:
                continue
            seen_category_keys.add(key)
            categories[row["category"]] = categories.get(row["category"], 0) + 1
        platforms = [row["platform"] for row in con.execute("SELECT DISTINCT platform FROM dashboard_messages WHERE platform != '' ORDER BY platform")]
        chats = [row["chat"] for row in con.execute("SELECT DISTINCT chat FROM dashboard_messages WHERE chat != '' ORDER BY chat")]
        total = sum(categories.values())
        return {
            "total": total,
            "matched_total": matched_total,
            "categories": categories,
            "platforms": platforms,
            "chats": chats,
            "records": [row_to_dict(row) for row in rows],
        }
    finally:
        con.close()


if __name__ == "__main__":
    con = connect()
    try:
        print(DB_PATH)
        print("messages", con.execute("SELECT COUNT(*) FROM dashboard_messages").fetchone()[0])
    finally:
        con.close()
