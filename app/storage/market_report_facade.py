#!/usr/bin/env python3
"""Backward-compatible entrypoint for market-report persistence."""
from __future__ import annotations

import os
from datetime import datetime

import push_history

if __package__ == "app":
    from .storage.market_reports import (
        CN_TZ,
        extract_decision_guidance,
        store_market_report as _store_market_report,
        to_cn_datetime,
    )
else:
    from storage.market_reports import (
        CN_TZ,
        extract_decision_guidance,
        store_market_report as _store_market_report,
        to_cn_datetime,
    )


_to_cn_datetime = to_cn_datetime


def store_market_report(
    content: str,
    *,
    job_id: str,
    title: str,
    run_dt: datetime | None = None,
) -> int:
    """Store one market report in the dashboard database without file output."""
    return _store_market_report(
        content,
        job_id=job_id,
        title=title,
        history_store=push_history,
        run_dt=run_dt,
        environ=os.environ,
        guidance_extractor=extract_decision_guidance,
    )
