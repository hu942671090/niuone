# Dashboard 指数行情完整恢复参考

Use this when repairing/rebuilding the `指数行情` tab in `~/.hermes/scripts/hermes_messages_dashboard.py`.

## Do not simplify the page

The user's expected 指数行情 page is not just four A-share index cards. A correct restore includes all major sections:

1. **A股 / 港股指数** — 上证指数、深证成指、创业板指、科创50、恒生指数
2. **美股夜盘** — 道琼斯、纳斯达克、标普500
3. **黄金 / 外汇 / 期货** — 富时A50、纽约黄金、现货黄金、美元人民币、美元指数
4. **行业指数 / 板块涨幅** — 中证/上证行业指数 list
5. **活跃股票榜** — 成交额前十、换手率前十、成交量前十

If only `/api/indices` cards render and sector/ranking sections are missing, the page is still broken.

## Backend helper architecture

The dashboard dynamically imports helper files from `~/.hermes/scripts/`:

- `indices_dashboard_api.py` → `/api/indices`
- `sectors_dashboard_api.py` → `/api/sectors`
- `hot_stocks_dashboard_api.py` → `/api/hot_stocks`
- `money_flow_dashboard_api.py` → `/api/money_flow`
- `market_flow_dashboard_api.py` → `/api/market_flow`

`/api/indices` should tolerate either legacy list output or richer dict output:

```python
raw_result = indices_mod.fetch_indices_data()
result = raw_result if isinstance(raw_result, dict) else {"items": raw_result}
```

Recommended richer shape:

```json
{
  "items": [...],
  "groups": {
    "domestic": [...],
    "global": [...],
    "commodity": [...]
  },
  "generated_at": "YYYY-MM-DD HH:MM:SS"
}
```

## Durable data-source choices

Eastmoney push2 APIs are often blocked on this machine, so prefer:

### Tencent `qt.gtimg.cn`

Use for A/H/US index real-time quotes and broad A-share stock quotes.

Examples:

```text
https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,r_hkHSI,usDJI,usIXIC,usINX
```

Important field mapping after split by `~`:

- `[1]` name
- `[3]` current price
- `[4]` previous close
- `[30]` timestamp (`YYYYMMDDHHMMSS` for A-share; formatted string for some overseas symbols)
- `[31]` change amount
- `[32]` change percent
- `[33]` high
- `[34]` low
- `[37]`成交额/金额-like field depending on symbol; for A-share stock quotes it is 万元
- `[38]`换手率 for A-share stock quotes

Do **not** display `[31]` as time; it is change amount.

A-share ranking data can be computed by querying a stock universe via Tencent quotes and sorting:

- `amount_top`: sort by `amount_wan` desc, display 成交额前十
- `turnover_top`: sort by `turnover` desc, display 换手率前十
- `volume_top`: sort by `volume_lot` desc, display 成交量前十

A practical universe source is `akshare.stock_info_a_code_name()` followed by Tencent quote batches. Avoid `akshare.stock_zh_a_spot_em()`, `stock_board_industry_name_em()`, and Eastmoney hot rank APIs when push2 is blocked.

### Tencent `ifzq.gtimg.cn`

Use for A-share index sparkline K-lines:

```text
https://ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,60,qfq
```

Critical: `param` is the full qt code (`sh000001`), not `sh` + `000001` duplicated. Response path: `data[qt_code].day`; close price is `k[2]`.

### Sina `hq.sinajs.cn`

Use for commodities / FX / futures when Tencent does not provide consistent `qt` quote parsing:

```text
https://hq.sinajs.cn/list=hf_CHA50CFD,hf_GC,hf_XAU,USDCNY,DINIW
```

Observed examples:

- `hf_CHA50CFD` — 富时中国A50期货
- `hf_GC` — 纽约黄金
- `hf_XAU` — 现货黄金
- `USDCNY` — 美元人民币
- `DINIW` — 美元指数

For `USDCNY` / `DINIW`, name/date fields differ from `hf_*`; verify by printing the raw comma split before finalizing field mappings.

## Frontend rendering checklist

`loadIndices()` should fetch all needed endpoints in parallel:

```javascript
const [idx, sec, hot, mf, mkf] = await Promise.all([
  fetch('/api/indices'),
  fetch('/api/sectors'),
  fetch('/api/hot_stocks'),
  fetch('/api/money_flow'),
  fetch('/api/market_flow')
]);
```

`renderIndicesPanel()` should render grouped index sections, not one flat strip:

- `renderIndexGroup('🇨🇳 A股 / 港股指数', domestic)`
- `renderIndexGroup('🌙 美股夜盘', global)`
- `renderIndexGroup('🥇 黄金 / 外汇 / 期货', commodity)`
- `📊 板块涨幅`
- `🔥 活跃股票榜` with three rank blocks

Remove stray `index-head` title rows that duplicate index names outside cards.

## Verification commands

Extract and syntax-check embedded JS before restart:

```bash
python3 - <<'PY'
from pathlib import Path
s=Path('~/.hermes/scripts/hermes_messages_dashboard.py').read_text()
html=s.split('INDEX_HTML = r"""',1)[1].split('"""',1)[0]
js=html.split('<script>',1)[1].split('</script>',1)[0]
Path('/tmp/dashboard.js').write_text(js)
PY
node --check /tmp/dashboard.js
```

Verify API completeness after restart:

```bash
python3 - <<'PY'
import urllib.request,json
for ep in ['indices','sectors','hot_stocks']:
    d=json.loads(urllib.request.urlopen(f'http://127.0.0.1:8787/api/{ep}', timeout=90).read().decode())
    print(ep, d.keys())
    if ep == 'indices': print(len(d.get('items',[])), {k:len(v) for k,v in d.get('groups',{}).items()})
    if ep == 'sectors': print(len(d.get('sectors',[])))
    if ep == 'hot_stocks': print(len(d.get('amount_top',[])), len(d.get('turnover_top',[])), len(d.get('volume_top',[])))
PY
```

Browser DOM assertions:

```javascript
({
  cards: document.querySelectorAll('.index-card').length,
  clouds: document.querySelectorAll('.sector-cloud').length,
  headings: [...document.querySelectorAll('#feed h3')].map(x => x.innerText)
})
```

Expected headings include `A股 / 港股指数`, `美股夜盘`, `黄金 / 外汇 / 期货`, `板块涨幅`, `活跃股票榜`, `成交额前十`, `换手率前十`, `成交量前十`.
