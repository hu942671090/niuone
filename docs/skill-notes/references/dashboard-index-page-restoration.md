# Dashboard Index Page Restoration & Verification Notes

Use this when maintaining `hermes_messages_dashboard.py` and the helper APIs behind the `指数行情` tab.

## Preserve the full `指数行情` information architecture

Do **not** simplify the page to just A-share index cards. The expected page includes:

- `📈 A股指数`: 上证指数、深证成指、创业板指、科创50, plus 伦敦金 if the user asks it to sit with A股指数
- `🌙 美股夜盘`: 道琼斯、纳斯达克、标普500
- `📈 板块涨跌幅`: 涨幅前十 + 跌幅前十
- `🔥 活跃股票榜`: 成交额前十 + 换手率前十; prefer 成交额 over 成交量 because成交额 better represents real资金参与强度, while成交量 is biased toward low-price stocks
- `💹 主力资金流向`: 行业主力净流入前十 + 主力净流出前十

If removing instruments by request, verify group membership explicitly. Example: removing 恒生指数、美元人民币、美元指数、富时A50、纽约黄金 while placing 伦敦金 alongside A股指数 should yield `domestic: 5`, `global: 3`, `commodity: 0`.

## Helper API files are part of the dashboard artifact

The main dashboard dynamically depends on sibling helper scripts:

- `indices_dashboard_api.py`
- `sectors_dashboard_api.py`
- `hot_stocks_dashboard_api.py`
- `money_flow_dashboard_api.py`
- `market_flow_dashboard_api.py`

When restoring from backup, rebuild all helpers before declaring the page fixed. Missing helpers often produce blank sections rather than obvious page-level failures.

## Run akshare-heavy helpers out-of-process

Some akshare paths can load native JS runtimes (e.g. mini_racer) and abort the parent Python process under the threaded HTTP server. Keep the dashboard service stable by executing helpers via subprocess and parsing JSON stdout, rather than importing akshare-heavy helper modules directly inside request handlers.

Pattern:

```python
def run_dashboard_helper(script_name, fallback, timeout=90):
    script = Path(__file__).with_name(script_name)
    try:
        raw = subprocess.check_output(
            [sys.executable, str(script)],
            text=True,
            timeout=timeout,
            stderr=subprocess.DEVNULL,
        )
        return json.loads(raw)
    except Exception as exc:
        return {**fallback, "error": str(exc)}
```

Each helper script must implement `if __name__ == '__main__': print(json.dumps(...))` so subprocess use returns valid JSON.

## Known data-source notes

- Eastmoney `stock_market_fund_flow()` / push2his may be blocked. Do not display fabricated or miscomputed `大盘资金流向`; return null values and let the frontend hide it if the data source is unavailable.
- `stock_fund_flow_industry(symbol="即时")` and `stock_fund_flow_concept(symbol="即时")` can provide usable sector/industry flow and涨跌幅 data.
- For live stock activity, prefer Tencent quote batches for 成交额/换手率 lists, with a short cache.

## Frontend failure checks

Before saying the dashboard is fixed:

1. Extract inline JS and run `node --check`.
2. Also fetch the externally served page (e.g. with browser-like User-Agent) and run `node --check` on the served JS; a local file check can miss stale/externally served syntax.
3. Check for duplicate declarations inside large functions (`Identifier 'timeTicks' has already been declared` broke the whole page and left it stuck at `加载中…`).
4. Verify in-browser that `typeof load === 'function'` and the feed no longer contains `加载中…`.

## Styling preference for the index page

Keep color semantics consistent across `板块涨跌幅`, `活跃股票榜`, and `主力资金流向`:

- 涨幅 / 净流入 / 上涨股: dark red background, subtle red border, red numeric text
- 跌幅 / 净流出 / 下跌股: dark green background, subtle green border, green numeric text
- Mobile: compact 3-column cards, small typography, and amount/turnover/flow values on their own line to avoid squeezing.
