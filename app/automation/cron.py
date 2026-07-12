"""Pure cron expression and scheduled-job domain rules."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping


@dataclass(frozen=True)
class Job:
    env_name: str
    default_expr: str
    job_id: str
    title: str
    command: tuple[str, ...]
    timeout_seconds: int = 180


@dataclass(frozen=True)
class JobRunResult:
    success: bool
    status: str
    exit_code: int | None = None
    elapsed: float = 0.0
    error: str = ""


def expand_field(part: str, low: int, high: int, *, dow: bool = False) -> set[int]:
    values: set[int] = set()
    for token in str(part or "").split(","):
        token = token.strip()
        if not token:
            continue
        base, _, step_text = token.partition("/")
        step = int(step_text) if step_text else 1
        if step <= 0:
            raise ValueError(f"invalid cron step: {part}")
        if base == "*":
            start, end = low, high
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(base)
        for value in range(start, end + 1, step):
            normalized = 0 if dow and value == 7 else value
            if low <= normalized <= high:
                values.add(normalized)
    return values


def cron_matches(
    expr: str,
    now: datetime,
    *,
    field_expander: Callable[..., set[int]] = expand_field,
) -> bool:
    minute, hour, day, month, dow = str(expr or "").split()
    cron_dow = 0 if now.isoweekday() == 7 else now.isoweekday()
    return (
        now.minute in field_expander(minute, 0, 59)
        and now.hour in field_expander(hour, 0, 23)
        and now.day in field_expander(day, 1, 31)
        and now.month in field_expander(month, 1, 12)
        and cron_dow in field_expander(dow, 0, 7, dow=True)
    )


def normalize_job_expr(job: Job, expr: str) -> str:
    raw = str(expr or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        hour_text, minute_text = raw.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"invalid time: {raw}")
        default_parts = job.default_expr.split()
        day, month, dow = default_parts[2:5] if len(default_parts) == 5 else ("*", "*", "*")
        return f"{minute} {hour} {day} {month} {dow}"
    return raw


def job_expr_value(
    job: Job,
    env_values: Mapping[str, str],
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    process_env = os.environ if environ is None else environ
    if job.env_name == "DASHBOARD_TIME_EXIT_TIME":
        return (
            env_values.get("DASHBOARD_TIME_EXIT_TIME")
            or process_env.get("DASHBOARD_TIME_EXIT_TIME")
            or env_values.get("DASHBOARD_TIME_STOP_EXIT_TIME")
            or process_env.get("DASHBOARD_TIME_STOP_EXIT_TIME")
            or job.default_expr
        )
    return env_values.get(job.env_name) or process_env.get(job.env_name) or job.default_expr
