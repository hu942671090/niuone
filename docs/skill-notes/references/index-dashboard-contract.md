# Index Dashboard Contract: Preserve Full Market Overview

This reference captures the expected shape of the `指数行情` dashboard page after the June 2026 repair session. Use it when restoring or refactoring `hermes_messages_dashboard.py` and its helper API files.

## Do not simplify the page

The user explicitly expects the index page to include more than the four A-share index cards. A "fix" that only restores 上证/深证/创业板/科创50 is incomplete and considered broken.

Expected sections:

1. `🇨🇳 A股 / 港股指数`
   - 上证指数, 深证成指, 创业板指, 科创50, 恒生指数
2. `🌙 美股夜盘`
   - 道琼斯, 纳斯达克, 标普500
3. `🥇 黄金 / 外汇 / 期货`
   - 富时A50, 纽约黄金, 现货黄金, 美元人民币, 美元指数
4. `📈 板块涨跌幅`
   - `📈 涨幅前十` red cards
   - `📉 跌幅前十` green cards
5. `🔥 活跃股票榜`
   - 成交额前十
   - 换手率前十
   - 成交量前十
6. `💹 主力资金流向`
   - `🔴 主力净流入前十` red cards, unit 亿
   - `🟢 主力净流出前十` green cards, unit 亿

Optional: a broad market flow summary may be shown if real data exists, but do not replace the industry main-fund-flow cards with a zero-filled placeholder.

## Helper API files and expected payloads

`hermes_messages_dashboard.py` dynamically imports helper modules in `~/.hermes/scripts/`.

### `indices_dashboard_api.py`

Recommended return shape from `fetch_indices_data()`:

```json
{
  "generated_at": "YYYY-MM-DD HH:MM:SS",
  "items": [
    {"key":"sh", "code":"sh000001", "name":"上证指数", "group":"domestic", "price":4163.10, "change_pct":1.78, "sparkline":[...], "time":"..."}
  ],
  "groups": {
    "domestic": [...],
    "global": [...],
    "commodity": [...]
  }
}
```

If `fetch_indices_data()` returns a dict, the dashboard route should pass it through directly. If it returns a list, wrap as `{items: list}` for backward compatibility.

Useful data sources:

- Tencent qt quotes: `https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,r_hkHSI,usDJI,usIXIC,usINX`
- Tencent A-share index K-line: `https://ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,60,qfq`
- Sina futures/FX/commodity: `https://hq.sinajs.cn/list=hf_CHA50CFD,hf_GC,hf_XAU,USDCNY,DINIW`

Tencent qt field notes:

- `parts[1]`: name
- `parts[3]`: current price
- `parts[4]`: previous close
- `parts[30]`: timestamp, often `YYYYMMDDHHMMSS` or already formatted
- `parts[31]`: change amount, **not** time
- `parts[32]`: change percent

### `sectors_dashboard_api.py`

Expected return shape:

```json
{
  "generated_at": "...",
  "count": 474,
  "gain_top": [{"name":"培育钻石", "price":2950.54, "pct":8.72, "source":"概念"}],
  "loss_top": [{"name":"自动化设备", "price":33529.0, "pct":-1.80, "source":"行业"}],
  "sectors": [same as gain_top for compatibility],
  "items": [same as gain_top for compatibility]
}
```

Usable akshare functions observed working on this machine:

```python
ak.stock_fund_flow_industry(symbol="即时")
ak.stock_fund_flow_concept(symbol="即时")
```

They return columns including `行业`, `行业指数`, and `行业-涨跌幅`. Combine industry+concept, dedupe by name, sort descending for gain_top and ascending for loss_top.

Avoid relying only on Eastmoney `stock_board_industry_name_em()` here; it may fail behind the local proxy/WAF and only gives one half of the old UI.

### `money_flow_dashboard_api.py`

Expected return shape:

```json
{
  "generated_at": "...",
  "count": 90,
  "inflow": [{"name":"证券", "price":1484.55, "pct":6.4, "net_flow_yi":156.05, "net_flow":15605000000}],
  "outflow": [{"name":"元件", "price":30679.0, "pct":-0.25, "net_flow_yi":-133.83, "net_flow":-13383000000}]
}
```

Use:

```python
ak.stock_fund_flow_industry(symbol="即时")
```

Columns: `行业`, `行业指数`, `行业-涨跌幅`, `流入资金`, `流出资金`, `净额`.
The values from this API are already in `亿`. Store both `net_flow_yi` for display and `net_flow = net_flow_yi * 100000000` for compatibility. Frontend should display `net_flow_yi` directly as `xx.xx亿`.

### `hot_stocks_dashboard_api.py`

Expected return shape:

```json
{
  "generated_at": "...",
  "universe_count": 3030,
  "quote_count": 3030,
  "amount_top": [...10],
  "turnover_top": [...10],
  "volume_top": [...10],
  "gain_top": [...10],
  "items": amount_top
}
```

Practical approach:

1. Get universe from `ak.stock_info_a_code_name()`.
2. Filter main-board-ish prefixes (`600`, `601`, `603`, `605`, `000`, `001`, `002`, `003`) and exclude ST/退.
3. Batch Tencent quotes via `https://qt.gtimg.cn/q=...`.
4. Parse:
   - `parts[2]`: code
   - `parts[1]`: name
   - `parts[3]`: price
   - `parts[32]`: pct
   - `parts[37]`: amount in 万元 → `amount_yi = amount_wan / 10000`
   - `parts[38]`: turnover rate %
   - `parts[36]` or `parts[6]`: volume lots
5. Cache 60-90 seconds to keep mobile page loading acceptable.

## Frontend rendering rules

`renderIndicesPanel()` should render sections by payload shape, not assume only `idx.items`:

- Use `idx.groups.domestic/global/commodity` if present.
- Render sector gain/loss using `sec.gain_top` and `sec.loss_top`.
- Render active stock rankings from `hot.amount_top`, `hot.turnover_top`, `hot.volume_top`.
- Render money flow cards from `moneyFlowData.inflow/outflow`, using `net_flow_yi` when available.
- Red cards = positive / inflow. Green cards = negative / outflow, matching China market color convention.

## Verification checklist

After a dashboard index repair:

```bash
node --check /tmp/dashboard.js
curl -s http://127.0.0.1:8787/api/indices      # expect items >= 12, groups domestic/global/commodity
curl -s http://127.0.0.1:8787/api/sectors      # expect gain_top=10, loss_top=10
curl -s http://127.0.0.1:8787/api/hot_stocks   # expect amount_top/turnover_top/volume_top each 10
curl -s http://127.0.0.1:8787/api/money_flow   # expect inflow=10, outflow=10
```

Browser DOM expectations on `/?category=indices`:

- `.index-card` count around 13
- Headings include `🌙 美股夜盘`, `🥇 黄金 / 外汇 / 期货`, `📈 涨幅前十`, `📉 跌幅前十`, `🔴 主力净流入前十`, `🟢 主力净流出前十`
- No zero-filled placeholder should be the only资金流 section.
