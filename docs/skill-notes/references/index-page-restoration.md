# Dashboard Index Page Restoration Notes (2026-06 session)

This note captures durable implementation details from restoring the `指数行情` page after it was accidentally simplified.

## User-facing contract

The `指数行情` tab is expected to be a full market overview, not just headline A-share indices. Preserve these modules unless the user explicitly asks to remove them:

1. **A股 / 港股指数** — 上证指数、深证成指、创业板指、科创50、恒生指数.
2. **美股夜盘** — 道琼斯、纳斯达克、标普500.
3. **黄金 / 外汇 / 期货** — 富时A50、纽约黄金、现货黄金、美元人民币、美元指数.
4. **板块涨跌幅** — two groups: `涨幅前十` and `跌幅前十`.
5. **活跃股票榜** — keep `成交额前十` and `换手率前十`; do not show `成交量前十` by default.
6. **主力资金流向** — two groups: `主力净流入前十` and `主力净流出前十`, with values in `亿`.

## Why 成交额 beats 成交量

For active-stock ranking, prefer `成交额` over `成交量` because volume is biased toward low-priced stocks. Amount better captures actual capital participation and market leadership. Pair it with `换手率` for chip activity.

## Visual style

Use the same palette across `板块涨跌幅`, `活跃股票榜`, and `主力资金流向`:

- Up / net inflow: `background: rgba(127,29,29,.28)`, `border-color: rgba(248,113,113,.22)`, value color `#fb7185`.
- Down / net outflow: `background: rgba(6,78,59,.28)`, `border-color: rgba(52,211,153,.22)`, value color `#34d399`.
- Mobile grids: 3 compact columns for small sector/rank cards; nested wide sections should stack vertically.

## Helper architecture pitfall

Do not directly import akshare-heavy helpers inside a threaded dashboard HTTP process. Some data paths may load native JS runtimes (MiniRacer/V8) and abort the entire server process. Instead, run helper API files out-of-process:

```python
def run_dashboard_helper(script_name: str, fallback: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    script = Path(__file__).with_name(script_name)
    try:
        raw = subprocess.check_output([sys.executable, str(script)], text=True, timeout=timeout, stderr=subprocess.DEVNULL)
        return json.loads(raw)
    except Exception as exc:
        return {**fallback, "error": str(exc)}
```

Route `/api/sectors`, `/api/hot_stocks`, and `/api/money_flow` through that helper. This isolates native crashes while preserving JSON responses.

## Data source notes

- `indices_dashboard_api.py`: Tencent `qt.gtimg.cn` for A/H/US indices; Sina `hq.sinajs.cn` for gold, A50, FX.
- `sectors_dashboard_api.py`: `akshare.stock_fund_flow_industry(symbol="即时")` + `akshare.stock_fund_flow_concept(symbol="即时")`; merge/dedupe and sort into `gain_top`/`loss_top`.
- `money_flow_dashboard_api.py`: `akshare.stock_fund_flow_industry(symbol="即时")`; `净额` is already in `亿`, so expose `net_flow_yi` and `net_flow = net_flow_yi * 1e8`.
- `hot_stocks_dashboard_api.py`: Tencent batch quotes over the main-board universe; return `amount_top`, `turnover_top`, and optionally `volume_top`, but default UI should show only amount + turnover.

## Verification checklist

After edits, verify:

```text
/api/indices -> items includes domestic/global/commodity groups
/api/sectors -> gain_top=10 and loss_top=10
/api/hot_stocks -> amount_top=10 and turnover_top=10
/api/money_flow -> inflow=10 and outflow=10
页面 headings include: 板块涨跌幅, 涨幅前十, 跌幅前十, 活跃股票榜, 成交额前十, 换手率前十, 主力资金流向
页面 headings do not include: 成交量前十 (unless explicitly requested)
```
