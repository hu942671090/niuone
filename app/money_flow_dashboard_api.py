#!/usr/bin/env python3
"""money_flow_dashboard_api.py — 行业主力资金流向（净流入/净流出前十）
使用 akshare.stock_fund_flow_industry(symbol='即时')，该接口当前可用且不是 Eastmoney push2 blocked path。
"""
import json
import os
import time
from pathlib import Path

from niuone_paths import get_dashboard_home

CACHE_BASE = get_dashboard_home(Path(__file__).resolve().parents[1]) / "cron" / "output"
CACHE_PATH = CACHE_BASE / "money_flow_dashboard_cache.json"
CACHE_TTL = 75


def _num(v):
    try:
        if v is None:
            return 0.0
        s = str(v).replace(',', '').replace('%', '').strip()
        if not s or s == 'nan':
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def _compute():
    import akshare as ak
    df = ak.stock_fund_flow_industry(symbol="即时")
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "name": str(r.get("行业", "")),
            "price": _num(r.get("行业指数")),
            "pct": _num(r.get("行业-涨跌幅")),
            # akshare 该接口单位已经是“亿”，前端 fmtAmount 对 net_flow 会转错；额外给 net_flow_yi
            "net_flow_yi": _num(r.get("净额")),
            "net_flow": _num(r.get("净额")) * 100000000,
            "inflow_yi": _num(r.get("流入资金")),
            "outflow_yi": _num(r.get("流出资金")),
            "leader": str(r.get("领涨股", "")),
            "leader_pct": _num(r.get("领涨股-涨跌幅")),
        })
    inflow = sorted(rows, key=lambda x: x["net_flow_yi"], reverse=True)[:10]
    outflow = sorted(rows, key=lambda x: x["net_flow_yi"])[:10]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "inflow": inflow,
        "outflow": outflow,
        "count": len(rows),
    }


def fetch_money_flow():
    try:
        if CACHE_PATH.exists() and time.time() - CACHE_PATH.stat().st_mtime < CACHE_TTL:
            return json.loads(CACHE_PATH.read_text())
        data = _compute()
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False))
        return data
    except Exception as e:
        return {"inflow": [], "outflow": [], "error": str(e)}

if __name__ == '__main__':
    print(json.dumps(fetch_money_flow(), ensure_ascii=False, indent=2))
