"""Pure context and media parsing for X posts."""
from __future__ import annotations

import html
import json
import re
import urllib.parse
from typing import Any


def has_recovered_context(post: dict[str, Any]) -> bool:
    return bool(
        str(post.get("reply_to_text") or post.get("reply_to_chinese_text") or "").strip()
        or str(post.get("quoted_text") or post.get("quoted_chinese_text") or "").strip()
        or post.get("reply_to_media")
        or post.get("quoted_media")
    )


def merge_media_items(*media_lists: object) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for media_items in media_lists:
        for item in media_items or []:
            if not isinstance(item, dict):
                continue
            url = normalize_media_url(item.get("url") or "")
            media_type = str(item.get("type") or "").strip() or media_type_from_url(url)
            if not is_x_post_media_url(url) or url in seen:
                continue
            seen.add(url)
            merged.append({"type": media_type, "url": url, "description": ""})
    return merged


def needs_context_repair(post: dict[str, Any]) -> bool:
    conversation_type = str(post.get("conversation_type") or "").lower()
    if conversation_type not in {"reply", "quote", "repost", "unknown"}:
        return False
    return not has_recovered_context(post)


def should_hold_for_context(post: dict[str, Any], *, strict: bool = False) -> bool:
    if not strict:
        return False
    conversation_type = str(post.get("conversation_type") or "").lower()
    return conversation_type in {"reply", "quote", "repost"} and not has_recovered_context(post)


def first_meta_content(raw: str, names: list[str] | tuple[str, ...]) -> str:
    for name in names:
        pattern = r'<meta[^>]+(?:property|name)=["\']' + re.escape(name) + r'["\'][^>]+content=["\']([^"\']*)["\']'
        match = re.search(pattern, raw, flags=re.I | re.S)
        if match:
            return html.unescape(match.group(1)).strip()
        pattern = r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(name) + r'["\']'
        match = re.search(pattern, raw, flags=re.I | re.S)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def normalize_media_url(url: object) -> str:
    value = html.unescape(str(url or "").strip()).replace("\\/", "/")
    if not value:
        return ""
    value = re.sub(r"[\"'<>\s].*$", "", value)
    if "pbs.twimg.com/media/" in value and "?" not in value and not re.search(
        r"\:(?:large|small|medium|orig)$", value, flags=re.I
    ):
        if re.search(r"\.(?:jpg|jpeg|png|webp)$", value, flags=re.I):
            value += ":large"
    return value


def is_x_post_media_url(url: object) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except Exception:
        return False
    if parsed.scheme != "https" or parsed.netloc.lower() != "pbs.twimg.com":
        return False
    return bool(re.match(r"^/(?:media|ext_tw_video_thumb|tweet_video_thumb)/", parsed.path))


def media_type_from_url(url: object) -> str:
    lower = str(url or "").lower()
    if ".mp4" in lower or "/video/" in lower:
        return "video"
    if ".gif" in lower or "tweet_video_thumb" in lower:
        return "gif"
    return "image"


def extract_media_from_value(value: object, seen_urls: set[str], media_items: list[dict[str, str]]) -> None:
    if isinstance(value, dict):
        for key in ("url", "contentUrl", "@id"):
            extract_media_from_value(value.get(key), seen_urls, media_items)
        return
    if isinstance(value, list):
        for item in value:
            extract_media_from_value(item, seen_urls, media_items)
        return
    url = normalize_media_url(value)
    if not is_x_post_media_url(url) or url in seen_urls:
        return
    seen_urls.add(url)
    media_items.append({"type": media_type_from_url(url), "url": url, "description": ""})


def extract_x_media(raw: str, social: dict[str, Any] | None = None) -> list[dict[str, str]]:
    media_items: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    social = social if isinstance(social, dict) else {}
    for key in ("image", "thumbnailUrl"):
        extract_media_from_value(social.get(key), seen_urls, media_items)
    for meta_name in ("og:image", "twitter:image", "twitter:image:src"):
        extract_media_from_value(first_meta_content(raw, [meta_name]), seen_urls, media_items)
    normalized_raw = html.unescape(str(raw or "")).replace("\\/", "/")
    pattern = r'https://pbs\.twimg\.com/(?:media|ext_tw_video_thumb|tweet_video_thumb)/[^"\'\\<>\s,) ]+'
    for match in re.finditer(pattern, normalized_raw):
        extract_media_from_value(match.group(0), seen_urls, media_items)
    return media_items


def parse_social_posting(raw: str) -> dict[str, Any]:
    for match in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', raw, flags=re.I | re.S):
        try:
            data = json.loads(html.unescape(match.group(1)))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "SocialMediaPosting":
            return data
    return {}
