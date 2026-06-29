#!/usr/bin/env python3
"""Rebuild NiuNiu practice account equity history from minute quotes.

This repair tool is intentionally narrow: it rebuilds a date range in
``equity_history`` and ``daily_equity_history`` from the local trade log plus
Eastmoney 1-minute A-share quotes fetched through akshare. It also rewrites the
matching rows in SQLite ``daily_equity``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".local-data" / "runtime" / "cron" / "output" / "niuniu_practice_portfolio.json"
DB_PATH = ROOT / ".local-data" / "runtime" / "niuniu.db"
CACHE_DIR = ROOT / ".local-data" / "runtime" / "cache" / "practice_equity_rebuild"
BACKUP_ROOT = ROOT / ".local-data" / "backups"
INITIAL_CASH_FALLBACK = 1_000_000.0


@dataclass(frozen=True)
class Trade:
    time: datetime
    action: str
    code: str
    name: str
    shares: int
    price: float
    amount: float
    commission: float
    transfer_fee: float
    stamp_duty: float

    @property
    def fees(self) -> float:
        return self.commission + self.transfer_fee + self.stamp_duty

    @property
    def cash_delta(self) -> float:
        if self.action == "BUY":
            return -(self.amount + self.fees)
        if self.action == "SELL":
            return self.amount - self.fees
        raise ValueError(f"Unsupported action: {self.action}")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def session_minutes(day: date) -> list[datetime]:
    points: list[datetime] = []
    cursor = datetime.combine(day, time(9, 30))
    while cursor <= datetime.combine(day, time(11, 30)):
        points.append(cursor)
        cursor += timedelta(minutes=1)
    cursor = datetime.combine(day, time(13, 1))
    while cursor <= datetime.combine(day, time(15, 0)):
        points.append(cursor)
        cursor += timedelta(minutes=1)
    return points


def round_money(value: float) -> float:
    return round(float(value), 2)


def load_state() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def load_db_daily_rows() -> dict[str, dict[str, Any]]:
    if not DB_PATH.exists():
        return {}
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT date, equity, cash, market_value, pnl_pct, created_at FROM daily_equity"
        ).fetchall()
    return {
        str(row[0]): {
            "date": row[0],
            "equity": float(row[1]),
            "cash": float(row[2]),
            "market_value": float(row[3]),
            "pnl_pct": float(row[4]),
            "created_at": row[5],
        }
        for row in rows
    }


def load_position_snapshot(snapshot_date: date) -> dict[str, int]:
    if not DB_PATH.exists():
        return {}
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT code, shares
            FROM position_snapshots
            WHERE date = ?
            ORDER BY code
            """,
            (snapshot_date.isoformat(),),
        ).fetchall()
    return {str(code): int(shares) for code, shares in rows if int(shares or 0) > 0}


def trade_from_raw(raw: dict[str, Any]) -> Trade | None:
    try:
        ts = parse_ts(str(raw.get("time") or ""))
    except Exception:
        return None
    action = str(raw.get("action") or "").upper()
    if action not in {"BUY", "SELL"}:
        return None
    code = str(raw.get("code") or "").zfill(6)
    shares = int(raw.get("shares") or 0)
    price = float(raw.get("price") or 0)
    if not code or shares <= 0 or price <= 0:
        return None
    amount = float(raw.get("amount") or 0)
    if amount <= 0:
        amount = shares * price
    return Trade(
        time=ts,
        action=action,
        code=code,
        name=str(raw.get("name") or ""),
        shares=shares,
        price=price,
        amount=amount,
        commission=float(raw.get("commission") or 0),
        transfer_fee=float(raw.get("transfer_fee") or 0),
        stamp_duty=float(raw.get("stamp_duty") or 0),
    )


def load_trades(state: dict[str, Any], start: date, end: date) -> list[Trade]:
    trades: list[Trade] = []
    for raw in state.get("trade_log") or []:
        if not isinstance(raw, dict):
            continue
        trade = trade_from_raw(raw)
        if not trade:
            continue
        if start <= trade.time.date() <= end:
            trades.append(trade)
    return sorted(trades, key=lambda item: item.time)


def apply_trade_to_positions(positions: dict[str, int], trade: Trade) -> None:
    if trade.action == "BUY":
        positions[trade.code] = positions.get(trade.code, 0) + trade.shares
    else:
        next_qty = positions.get(trade.code, 0) - trade.shares
        if next_qty > 0:
            positions[trade.code] = next_qty
        else:
            positions.pop(trade.code, None)


def reverse_trade_in_place(positions: dict[str, int], trade: Trade) -> None:
    if trade.action == "BUY":
        next_qty = positions.get(trade.code, 0) - trade.shares
        if next_qty > 0:
            positions[trade.code] = next_qty
        else:
            positions.pop(trade.code, None)
    else:
        positions[trade.code] = positions.get(trade.code, 0) + trade.shares


def trade_effective_minute(trade: Trade) -> datetime:
    minute = trade.time.replace(second=0, microsecond=0)
    if trade.time.second or trade.time.microsecond:
        minute += timedelta(minutes=1)
    return minute


def infer_needed_codes(start_positions: dict[str, int], days: list[date], trades: list[Trade]) -> dict[date, set[str]]:
    by_day: dict[date, list[Trade]] = defaultdict(list)
    for trade in trades:
        by_day[trade.time.date()].append(trade)

    positions = dict(start_positions)
    needed: dict[date, set[str]] = {}
    for day in days:
        codes = set(positions)
        codes.update(trade.code for trade in by_day.get(day, []))
        needed[day] = codes
        for trade in by_day.get(day, []):
            apply_trade_to_positions(positions, trade)
    return needed


def cache_path(code: str, day: date) -> Path:
    return CACHE_DIR / f"{code}_{day.isoformat()}_1m.json"


def fetch_minute_prices(code: str, day: date, *, refresh: bool = False) -> dict[datetime, float]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(code, day)
    if path.exists() and not refresh:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            parse_ts(row["time"]): float(row["close"])
            for row in payload.get("rows", [])
            if row.get("time") and row.get("close") is not None
        }

    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        raise RuntimeError("akshare is required; run this with .local-data/.venv/bin/python") from exc

    df = ak.stock_zh_a_hist_min_em(
        symbol=code,
        start_date=f"{day.isoformat()} 09:30:00",
        end_date=f"{day.isoformat()} 15:00:00",
        period="1",
        adjust="",
    )
    if df is None or df.empty:
        raise RuntimeError(f"No minute quote data for {code} on {day.isoformat()}")

    rows: list[dict[str, Any]] = []
    series: dict[datetime, float] = {}
    for _, row in df.iterrows():
        time_text = str(row.get("时间") or "")
        close = row.get("收盘")
        if not time_text or close is None:
            continue
        try:
            ts = parse_ts(time_text[:19])
            price = float(close)
        except Exception:
            continue
        if ts.date() != day:
            continue
        series[ts] = price
        rows.append({"time": ts.strftime("%Y-%m-%d %H:%M:%S"), "close": price})

    if not series:
        raise RuntimeError(f"No usable minute quote data for {code} on {day.isoformat()}")

    payload = {
        "source": "akshare.stock_zh_a_hist_min_em",
        "symbol": code,
        "date": day.isoformat(),
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return series


def load_price_book(needed_codes: dict[date, set[str]], *, refresh: bool = False) -> dict[date, dict[str, dict[datetime, float]]]:
    price_book: dict[date, dict[str, dict[datetime, float]]] = {}
    total = sum(len(codes) for codes in needed_codes.values())
    done = 0
    for day in sorted(needed_codes):
        day_prices: dict[str, dict[datetime, float]] = {}
        for code in sorted(needed_codes[day]):
            done += 1
            print(f"[fetch] {done}/{total} {day.isoformat()} {code}", flush=True)
            day_prices[code] = fetch_minute_prices(code, day, refresh=refresh)
        price_book[day] = day_prices
    return price_book


def price_at_or_before(series: dict[datetime, float], target: datetime) -> float | None:
    candidates = [ts for ts in series if ts <= target]
    if not candidates:
        return None
    return series[max(candidates)]


def build_start_state(
    start: date,
    trades: list[Trade],
    db_daily: dict[str, dict[str, Any]],
) -> tuple[dict[str, int], float]:
    end_positions = load_position_snapshot(start)
    if not end_positions:
        raise RuntimeError(f"No position snapshot found for {start.isoformat()}")
    daily_row = db_daily.get(start.isoformat())
    if not daily_row:
        raise RuntimeError(f"No daily_equity row found for {start.isoformat()}")

    positions = dict(end_positions)
    cash = float(daily_row["cash"])
    start_trades = [trade for trade in trades if trade.time.date() == start]
    for trade in sorted(start_trades, key=lambda item: item.time, reverse=True):
        reverse_trade_in_place(positions, trade)
        cash -= trade.cash_delta
    return {code: qty for code, qty in positions.items() if qty > 0}, cash


def market_value_for_positions(
    positions: dict[str, int],
    day: date,
    day_prices: dict[str, dict[datetime, float]],
    last_prices: dict[str, float],
    *,
    target: datetime | None = None,
) -> float:
    market_value = 0.0
    target = target or datetime.combine(day, time(15, 0))
    for code, qty in positions.items():
        if qty <= 0:
            continue
        series = day_prices.get(code) or {}
        price = price_at_or_before(series, target)
        if price is None:
            price = last_prices.get(code)
        if price is None:
            raise RuntimeError(f"Missing price for held code {code} at {target}")
        last_prices[code] = price
        market_value += qty * price
    return market_value


def make_equity_point(
    ts: datetime,
    cash: float,
    market_value: float,
    initial_cash: float,
) -> dict[str, Any]:
    equity = cash + market_value
    return {
        "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "equity": round_money(equity),
        "cash": round_money(cash),
        "market_value": round_money(market_value),
        "pnl_pct": round_money((equity / initial_cash - 1) * 100) if initial_cash > 0 else 0.0,
    }


def rebuild_history(
    state: dict[str, Any],
    start: date,
    end: date,
    *,
    refresh: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    days = date_range(start, end)
    db_daily = load_db_daily_rows()
    trades = load_trades(state, start, end)
    start_positions, start_cash = build_start_state(start, trades, db_daily)

    needed_codes = infer_needed_codes(start_positions, days, trades)
    price_book = load_price_book(needed_codes, refresh=refresh)

    initial_cash = float(state.get("initial_cash") or INITIAL_CASH_FALLBACK)
    by_day: dict[date, list[Trade]] = defaultdict(list)
    for trade in trades:
        by_day[trade.time.date()].append(trade)
    for day_trades in by_day.values():
        day_trades.sort(key=lambda item: item.time)

    cash = start_cash
    positions = dict(start_positions)
    last_prices: dict[str, float] = {}
    session_points: list[dict[str, Any]] = []
    daily_points: list[dict[str, Any]] = []
    daily_summaries: dict[str, Any] = {}

    for day in days:
        day_prices = price_book[day]
        day_trades = by_day.get(day, [])
        trade_index = 0

        for minute in session_minutes(day):
            while trade_index < len(day_trades) and trade_effective_minute(day_trades[trade_index]) <= minute:
                trade = day_trades[trade_index]
                cash += trade.cash_delta
                apply_trade_to_positions(positions, trade)
                trade_index += 1

            for code, series in day_prices.items():
                price = series.get(minute)
                if price is not None:
                    last_prices[code] = price

            market_value = 0.0
            for code, qty in positions.items():
                price = last_prices.get(code)
                if price is None:
                    series = day_prices.get(code) or {}
                    price = price_at_or_before(series, minute)
                    if price is not None:
                        last_prices[code] = price
                if price is None:
                    raise RuntimeError(f"Missing minute price for held code {code} at {minute}")
                market_value += qty * price
            session_points.append(make_equity_point(minute, cash, market_value, initial_cash))

        while trade_index < len(day_trades):
            trade = day_trades[trade_index]
            cash += trade.cash_delta
            apply_trade_to_positions(positions, trade)
            trade_index += 1

        close_market_value = market_value_for_positions(
            positions,
            day,
            day_prices,
            last_prices,
            target=datetime.combine(day, time(15, 0)),
        )
        created_at = str(db_daily.get(day.isoformat(), {}).get("created_at") or f"{day.isoformat()} 15:00:00")
        daily_point = make_equity_point(parse_ts(created_at), cash, close_market_value, initial_cash)
        daily_points.append(daily_point)
        daily_summaries[day.isoformat()] = {
            "session_points": len([p for p in session_points if p["time"].startswith(day.isoformat())]),
            "trades": len(day_trades),
            "cash": daily_point["cash"],
            "market_value": daily_point["market_value"],
            "equity": daily_point["equity"],
            "pnl_pct": daily_point["pnl_pct"],
            "positions": dict(sorted(positions.items())),
        }

    meta = {
        "start_positions": dict(sorted(start_positions.items())),
        "start_cash": round_money(start_cash),
        "needed_codes": {day.isoformat(): sorted(codes) for day, codes in needed_codes.items()},
        "daily": daily_summaries,
    }
    return session_points, daily_points, meta


def backup_runtime_files() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"practice_equity_rebuild_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    if STATE_PATH.exists():
        shutil.copy2(STATE_PATH, backup_dir / STATE_PATH.name)
    if DB_PATH.exists():
        backup_db = backup_dir / DB_PATH.name
        with sqlite3.connect(DB_PATH) as src, sqlite3.connect(backup_db) as dst:
            src.backup(dst)
    return backup_dir


def merge_state_points(
    state: dict[str, Any],
    start: date,
    end: date,
    session_points: list[dict[str, Any]],
    daily_points: list[dict[str, Any]],
) -> dict[str, Any]:
    def outside_target(point: dict[str, Any]) -> bool:
        text = str(point.get("time") or "")[:10]
        try:
            point_date = parse_date(text)
        except Exception:
            return True
        return not (start <= point_date <= end)

    next_state = dict(state)
    history = [p for p in state.get("equity_history", []) if isinstance(p, dict) and outside_target(p)]
    history.extend(session_points)
    history.sort(key=lambda item: str(item.get("time") or ""))
    next_state["equity_history"] = history[-2000:]

    daily_history = [p for p in state.get("daily_equity_history", []) if isinstance(p, dict) and outside_target(p)]
    daily_history.extend(daily_points)
    daily_history.sort(key=lambda item: str(item.get("time") or ""))
    next_state["daily_equity_history"] = daily_history[-260:]
    next_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return next_state


def write_state(state: dict[str, Any]) -> None:
    tmp_path = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(STATE_PATH)


def write_daily_equity(daily_points: list[dict[str, Any]]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("BEGIN")
        for point in daily_points:
            row_date = str(point["time"])[:10]
            conn.execute(
                """
                INSERT OR REPLACE INTO daily_equity
                    (date, equity, cash, market_value, pnl_pct, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row_date,
                    point["equity"],
                    point["cash"],
                    point["market_value"],
                    point["pnl_pct"],
                    point["time"],
                ),
            )
        conn.commit()


def print_summary(session_points: list[dict[str, Any]], daily_points: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    print("\n[start]")
    print(f"cash={meta['start_cash']:.2f} positions={meta['start_positions']}")
    print("\n[needed codes]")
    for day, codes in meta["needed_codes"].items():
        print(f"{day}: {', '.join(codes)}")
    print("\n[rebuilt daily]")
    for point in daily_points:
        date_text = str(point["time"])[:10]
        info = meta["daily"][date_text]
        print(
            f"{date_text}: points={info['session_points']} trades={info['trades']} "
            f"cash={point['cash']:.2f} mv={point['market_value']:.2f} "
            f"equity={point['equity']:.2f} pnl_pct={point['pnl_pct']:.2f}"
        )
    print(f"\n[session points] {len(session_points)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--refresh", action="store_true", help="Ignore cached quotes and fetch from network.")
    parser.add_argument("--apply", action="store_true", help="Write rebuilt data to JSON and SQLite.")
    args = parser.parse_args()

    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if end < start:
        raise SystemExit("--end-date must be >= --start-date")
    if not STATE_PATH.exists():
        raise SystemExit(f"Missing state file: {STATE_PATH}")
    if not DB_PATH.exists():
        raise SystemExit(f"Missing database: {DB_PATH}")

    state = load_state()
    session_points, daily_points, meta = rebuild_history(state, start, end, refresh=args.refresh)
    print_summary(session_points, daily_points, meta)

    if not args.apply:
        print("\n[dry-run] No files were written. Re-run with --apply to rewrite state and DB.")
        return 0

    backup_dir = backup_runtime_files()
    next_state = merge_state_points(state, start, end, session_points, daily_points)
    write_state(next_state)
    write_daily_equity(daily_points)
    print(f"\n[applied] backup={backup_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
