"""Pure text formatting for X dashboard records."""
from __future__ import annotations

from typing import Any


def display_text(primary: object, fallback: object = "") -> str:
    text = str(primary or "").strip() or str(fallback or "").strip()
    if not text:
        return ""
    markers = ["中文翻译：", "翻译：", "Chinese translation:", "Translation:", "中文："]
    lower = text.lower()
    for marker in markers:
        index = lower.find(marker.lower())
        if index >= 0:
            cleaned = text[index + len(marker):].strip()
            return cleaned or text
    return text


def fmt_media_items(title: str, media_items: list[dict[str, Any]], indent: str = "", include_urls: bool = True) -> list[str]:
    if not include_urls:
        return []
    lines: list[str] = []
    item_index = 1
    for item in media_items or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        media_type = str(item.get("type") or "媒体").strip() or "媒体"
        label = f"{title}{item_index}" if len(media_items or []) > 1 else title
        if url:
            lines.append(f"{indent}{label}（{media_type}）：{url}")
        item_index += 1
    return lines


def fmt_text_box(
    title: str,
    author: object,
    text: object,
    media_items: list[dict[str, Any]] | None = None,
    indent: str = "",
    include_media_urls: bool = True,
) -> list[str]:
    text_value = str(text or "").strip()
    author_value = str(author or "").strip()
    media_lines = fmt_media_items("媒体", media_items or [], indent="", include_urls=include_media_urls)
    if not text_value and not media_lines:
        return []
    header = title + (f"｜{author_value}" if author_value else "")
    lines = [header]
    if text_value:
        lines.append(text_value)
    lines.extend(media_lines)
    return lines


def fmt_missing_context(conversation_type: str, missing_reason: str) -> str:
    if conversation_type == "reply":
        return "⚠️ 回复上下文：本次未取到被回复原推。" + (f"原因：{missing_reason}" if missing_reason else "")
    if conversation_type in {"quote", "repost"}:
        return "⚠️ 引用/转推上下文：本次未取到被引用原推。" + (f"原因：{missing_reason}" if missing_reason else "")
    if missing_reason:
        return f"⚠️ 上下文状态：{missing_reason}"
    return ""


def fmt_post(index: int, display_name: str, post: dict[str, Any], include_media_urls: bool = True) -> str:
    del index  # Retained for the legacy call signature.
    time_text = post.get("time") or "时间未知"
    text = display_text(post.get("chinese_text"), post.get("full_text"))
    reply_text = display_text(post.get("reply_to_chinese_text"), post.get("reply_to_text"))
    quoted_text = display_text(post.get("quoted_chinese_text"), post.get("quoted_text"))
    conversation_type = str(post.get("conversation_type") or "").lower()
    missing_reason = str(post.get("context_missing_reason") or "").strip()
    lines: list[str] = []

    if reply_text:
        lines.extend(fmt_text_box("原帖", post.get("reply_to_author"), reply_text, post.get("reply_to_media") or [], include_media_urls=include_media_urls))
        lines.extend(["", f"回复｜{display_name}｜{time_text}", text or "（无正文）"])
    elif quoted_text:
        lines.extend(fmt_text_box("引用原帖", post.get("quoted_author"), quoted_text, post.get("quoted_media") or [], include_media_urls=include_media_urls))
        lines.extend(["", f"评论/转述｜{display_name}｜{time_text}", text or "（无正文）"])
    else:
        lines.extend([f"{display_name}｜{time_text}", text or "（无正文）"])
        missing_line = fmt_missing_context(conversation_type, missing_reason)
        if missing_line:
            lines.extend(["", missing_line])

    media_lines = fmt_media_items("图片/媒体", post.get("media") or [], include_urls=include_media_urls)
    if media_lines:
        lines.append("")
        lines.extend(media_lines)
    return "\n".join(lines)
