"""Pure timestamp and retry-state rules for X monitoring."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .content import has_recovered_context


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def parse_post_time(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    text = re.sub(r"\s*(北京时间|GMT|UTC)$", "", text, flags=re.I).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    parsed = parse_iso(text)
    return parsed.replace(tzinfo=None) if parsed else None


def is_newer_post(post: dict[str, Any], latest_value: dict[str, Any] | None, post_id: object) -> bool:
    latest_time = parse_post_time((latest_value or {}).get("time"))
    post_time = parse_post_time(post.get("time"))
    if latest_time and post_time:
        return post_time > latest_time
    latest_id = str((latest_value or {}).get("post_id") or "").strip()
    return bool(post_id and post_id != latest_id)


def choose_latest_value(existing_latest: dict[str, Any] | None, posts: list[dict[str, Any]], display_name: str) -> dict[str, Any]:
    newest_post = None
    newest_time = None
    for post in posts or []:
        post_time = parse_post_time(post.get("time"))
        if post_time and (newest_time is None or post_time > newest_time):
            newest_post = post
            newest_time = post_time
    if newest_post is None and posts:
        newest_post = posts[0]
    if newest_post is None:
        return existing_latest or {}

    candidate = {
        "post_id": str(newest_post.get("post_id") or "").strip(),
        "time": newest_post.get("time"),
        "display_name": display_name,
    }
    existing_time = parse_post_time((existing_latest or {}).get("time"))
    if existing_time and newest_time and existing_time >= newest_time:
        return existing_latest or {}
    return candidate


def merge_seen_ids(seen: dict[str, list[str]], pending_seen_ids: dict[str, list[object]] | None) -> None:
    for handle, post_ids in (pending_seen_ids or {}).items():
        existing = list(seen.get(handle, []))
        existing_set = {str(item) for item in existing}
        for post_id in post_ids:
            post_id = str(post_id)
            if post_id and post_id not in existing_set:
                existing.append(post_id)
                existing_set.add(post_id)
        seen[handle] = existing[-80:]


def merge_latest(latest: dict[str, dict[str, Any]], pending_latest: dict[str, dict[str, Any]] | None) -> None:
    for handle, value in (pending_latest or {}).items():
        current_time = parse_post_time((latest.get(handle) or {}).get("time"))
        value_time = parse_post_time((value or {}).get("time"))
        if not current_time or not value_time or value_time >= current_time:
            latest[handle] = value


def latest_from_items(items: list[tuple[str, dict[str, Any], object, str]], existing_latest: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    by_handle_posts: dict[str, list[dict[str, Any]]] = {}
    by_handle_display: dict[str, str] = {}
    for display_name, post, _post_id, handle in items:
        by_handle_posts.setdefault(handle, []).append(post)
        by_handle_display[handle] = display_name
    for handle, posts in by_handle_posts.items():
        result[handle] = choose_latest_value(
            (existing_latest or {}).get(handle) or {}, posts, by_handle_display.get(handle) or handle
        )
    return result


def pending_is_already_latest(state: dict[str, Any]) -> bool:
    pending_latest = (state.get("pending_delivery") or {}).get("latest") or {}
    latest = state.get("latest") or {}
    if not pending_latest:
        return False
    return all(
        str((latest.get(handle) or {}).get("post_id") or "") == str(pending_value.get("post_id") or "")
        for handle, pending_value in pending_latest.items()
    )


def parse_any_datetime(value: object) -> datetime | None:
    if not value:
        return None
    parsed = parse_iso(str(value).strip())
    if parsed:
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    post_time = parse_post_time(value)
    return post_time.replace(tzinfo=timezone(timedelta(hours=8))) if post_time else None


def job_ran_after_pending(job: dict[str, Any], pending: dict[str, Any]) -> bool:
    pending_time = parse_any_datetime((pending or {}).get("created_at"))
    job_time = parse_any_datetime((job or {}).get("last_run_at"))
    return bool(pending_time and job_time and job_time >= pending_time)


def needs_context_hydration(post: dict[str, Any]) -> bool:
    if str(post.get("conversation_type") or "").lower() in {"reply", "quote", "repost"}:
        return True
    fields = ("reply_to_author", "reply_to_text", "reply_to_chinese_text", "quoted_author", "quoted_text", "quoted_chinese_text")
    return any(str(post.get(field) or "").strip() for field in fields)


def looks_like_x_handle(value: object) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]{1,15}", str(value or "").lstrip("@")))


def sent_context_key(handle: object, post_id: object) -> str:
    return f"{str(handle or '').lstrip('@').lower()}:{str(post_id or '').strip()}"


def should_retry_sent_context(post: dict[str, Any]) -> bool:
    conversation_type = str(post.get("conversation_type") or "").lower()
    if conversation_type in {"reply", "quote", "repost"} and not has_recovered_context(post):
        return True
    return bool(str(post.get("context_missing_reason") or "").strip() and not has_recovered_context(post))


def compact_sent_context_entry(entry: dict[str, Any]) -> dict[str, Any]:
    keep_keys = {
        "key", "handle", "display_name", "post_id", "time", "post", "queued_at",
        "updated_at", "attempts", "last_attempt_at", "last_error", "source_type",
        "source_id", "source_label", "platform", "platform_label", "chat",
        "chat_label", "external_id", "title", "kind", "delivery", "raw_path",
        "timestamp", "created_at", "db_id",
    }
    return {key: entry.get(key) for key in keep_keys if entry.get(key) not in (None, "")}
