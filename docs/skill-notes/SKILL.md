---
name: dashboard-financial-charts
description: "Build interactive financial dashboards with real-time charts, benchmark comparisons, and trading simulation visualizations for A-share markets."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [dashboard, financial, charts, a-share, trading, visualization]
    homepage: https://hermes-agent.nousresearch.com/docs
    related_skills: [cn-stock-b1-screening, niuniu-practice-rules]
---

# Dashboard Financial Charts

Build interactive financial dashboards with real-time charts, benchmark comparisons, and trading simulation visualizations for A-share markets.

## When to Use This Skill

Use this skill when:
- Building dashboard visualizations for stock/portfolio performance
- Adding benchmark comparison curves (indices like 上证指数, 沪深300, 创业板指, 科创50)
- Creating trading simulation interfaces with real-time data
- Implementing responsive financial charts with dark/light themes
- Integrating multiple data sources (Tencent, Sina, Eastmoney APIs)

## Core Components

### 1. Benchmark Comparison Curves

**Purpose**: Show portfolio performance against market indices for relative performance analysis.

**Implementation**:
```javascript
// 1. Define benchmark configuration
let benchmarkOverlay = {
  sh000001: true,  // 上证指数
  sh000300: true,  // 沪深300
  sz399006: true,  // 创业板指
  sh000688: true   // 科创50
};

// 2. Color scheme
const benchmarkColors = {
  sh000001: '#f59e0b',  // 橙色
  sh000300: '#60a5fa',  // 蓝色
  sz399006: '#ec4899',  // 粉红
  sh000688: '#8b5cf6'   // 紫色
};

// 3. Data fetching (with 60-second cache)
async function fetchBenchmarks() {
  const res = await fetch('/api/practice_benchmarks');
  return await res.json();
}
```

**Data Sources**:
- **腾讯分钟线**: `https://qt.gtimg.cn/q=sh000001,sh000300&type=minute`
- **缓存策略**: 60秒缓存避免频繁请求
- **备用数据源**: Tencent → Eastmoney → Sina fallback chain

### 2. Percentage-Based Y-Axis

**Why**: Portfolio value and indices should use percentage change for meaningful comparison, not absolute values.

**Implementation**:
```javascript
// Convert equity values to percentage change
function normalizeToPercentage(values, initialValue) {
  return values.map(v => ((v - initialValue) / initialValue) * 100);
}

// Y-axis scaling function
function yScale(percent) {
  const min = Math.min(...percentages);
  const max = Math.max(...percentages);
  const range = max - min || 1;
  return height - margin - ((percent - min) / range) * chartHeight;
}
```

### 3. Responsive Chart Design

**Mobile-first approach**:
```css
/* Base chart container */
.practice-curve {
  height: 120px;
  width: 100%;
  margin-top: 8px;
}

/* Mobile responsive */
@media (max-width: 720px) {
  .practice-curve {
    height: 100px;
  }
  .benchmark-toggle {
    padding: 4px 8px;
    font-size: 12px;
  }
}
```

### 4. Interactive Toggle Controls

**User interface pattern**:
```html
<div class="benchmark-controls">
  <button class="benchmark-toggle active" data-symbol="sh000001">
    上证指数
  </button>
  <button class="benchmark-toggle" data-symbol="sh000300">
    沪深300
  </button>
  <!-- ... more benchmarks -->
</div>
```

**Toggle logic**:
```javascript
function toggleBenchmark(symbol) {
  benchmarkOverlay[symbol] = !benchmarkOverlay[symbol];
  updateChart();
  updateToggleButton(symbol);
}
```

## Key Implementation Patterns

### 1. Data Caching Strategy

```python
# Backend caching (Python)
import time
from functools import lru_cache

@lru_cache(maxsize=1)
def get_benchmark_data_with_cache():
    current_minute = int(time.time() / 60)
    # Cache for 60 seconds
    if not hasattr(get_benchmark_data_with_cache, 'last_fetch') or \
       current_minute - get_benchmark_data_with_cache.last_fetch >= 1:
        data = fetch_tencent_minute_data()
        get_benchmark_data_with_cache.last_fetch = current_minute
        return data
    return get_benchmark_data_with_cache.cached_data
```

### 2. Multi-Source Fallback

```python
def get_stock_quote_with_fallback(symbol):
    """四级冗余报价链：腾讯→东方财富→Sina→单票"""
    try:
        # 1. 腾讯实时
        return fetch_tencent_quote(symbol)
    except Exception as e1:
        try:
            # 2. 东方财富
            return fetch_eastmoney_quote(symbol)
        except Exception as e2:
            try:
                # 3. Sina
                return fetch_sina_quote(symbol)
            except Exception as e3:
                # 4. 单票兜底
                return get_last_known_price(symbol)
```

### 3. SVG Chart Rendering

```javascript
function renderPracticeCurve(points, initialValue, benchmarks) {
  const w = 800, h = 120;
  const margin = 12;
  
  // Main portfolio line
  const portfolioLine = generatePath(points, w, h, margin);
  
  // Benchmark lines
  const benchmarkPaths = benchmarks.items
    .filter(b => benchmarkOverlay[b.symbol])
    .map(b => ({
      d: generatePath(b.points, w, h, margin),
      color: benchmarkColors[b.symbol],
      name: b.name
    }));
  
  return `
    <svg class="practice-curve" viewBox="0 0 ${w} ${h}">
      <path class="area" d="${portfolioLine} L${w} ${h} L0 ${h} Z" 
            fill="currentColor" opacity=".12"></path>
      <path class="line" d="${portfolioLine}" 
            style="fill:none;stroke:currentColor;stroke-width:2.6"></path>
      ${benchmarkPaths.map(b => `
        <path d="${b.d}" fill="none" stroke="${b.color}" 
              stroke-width="1.8" opacity=".92"></path>
      `).join('')}
    </svg>
  `;
}
```

## User Preferences & Constraints

Based on user feedback, implement these preferences:

### 1. Visual Design
- **Dark theme preferred** with Linear-style UI
- **Compact tables**: stock code only (no company names), price only (no % change)
- **Minimal padding** to fit more content
- **Responsive**: 4-col → 2-col below 720px, smaller fonts

### 2. Data Presentation
- **Benchmark lines**: Solid lines (not dashed) for clarity
- **Default state**: All benchmarks visible by default
- **Bottom stats**: Show latest % change for each benchmark
- **Y-axis**: Percentage-based for fair comparison

### 3. Trading Rules Display
- Show model and provider info (e.g., "deepseek-v4-flash-free | OpenCode Zen")
- Display trading constraints: "A股模拟：100股整数倍、T+1、非交易时段不执行买卖"

## Common Pitfalls & Solutions

### 0. JS Syntax: Literal `\n` in Template Strings

**Problem**: When editing the dashboard Python file (which contains a raw triple-quoted HTML string), accidentally inserting literal backslash-n (`\n`) characters instead of real newlines inside `<script>` blocks causes `SyntaxError: Invalid or unexpected token` at runtime. The entire JS fails to parse — tabs don't render, feed stays "加载中…".

**Detection**: Run `node --check` on the extracted JS:
```bash
python3 -c "from pathlib import Path; s=Path('hermes_messages_dashboard.py').read_text(); html=s.split('INDEX_HTML = r\"\"\"',1)[1].split('\"\"\"',1)[0]; js=html.split('<script>',1)[1].split('</script>',1)[0]; Path('/tmp/dashboard.js').write_text(js)"
node --check /tmp/dashboard.js
```

**Fix**: Replace literal `\n\n\n` with real newlines in the Python source. Never use `\n` as a separator between JS function definitions — use actual blank lines.

### 0.1 Stuck “加载中…” with APIs returning 200

**Problem**: The dashboard HTML and JSON APIs may all return 200 while a category page (especially `牛牛实战`) remains stuck on `加载中…`. This often means a client-side render exception occurred after async data loaded, not that the backend/tunnel is down.

**Concrete pitfall from `renderPracticeCurve`:** If the function signature is `renderPracticeCurve(history, dailyHistory, initialCash, benchmarks)`, call it with all four arguments. Passing `(equity_history, initialCash, benchmarks)` shifts `initialCash` into `dailyHistory` and can expose hidden JS bugs. Also initialize SVG layout constants (`w`, `h`, `left`, `right`, `top`, `bottom`, `innerW`, `innerH`, `totalSessionMinutes`) before any branch or closure uses them; date-mode branches that reference `left` before declaration fail with `ReferenceError: Cannot access 'left' before initialization`.

**Debug workflow:**
1. Verify backend endpoints independently (`/api/b1_screen`, `/api/niuniu_practice`, `/api/practice_benchmarks`). If they return payloads, keep debugging the frontend.
2. Use the browser console to inspect `document.querySelector('#feed').innerText` and evaluate a small render probe such as `renderPracticePanel()`; this surfaces the actual JS stack trace.
3. Extract and run `node --check` on the embedded script to catch syntax errors, then use browser-console evaluation for runtime errors.
4. After patching, restart/reload the dashboard, open `/?category=b1_screen` with a cache-busting query parameter, and verify the feed contains account stats,收益曲线, positions, strategy performance, and candidate cards.

See `references/niuniu-practice-loading-debug.md` for the session-specific reproduction and fix notes.

### 0.2 Scaling public dashboards to ~1000 viewers

**Problem**: A Python `ThreadingHTTPServer` dashboard with `setInterval(..., 5000)` and uncached `no-store` API responses does not scale to large public audiences. In this dashboard, `/api/messages` was ~1.68MB before limiting, and `/api/niuniu_practice` could take ~1.6s because it refreshes realtime quotes/account state. 1000 viewers refreshing every 5s can create hundreds of repeated origin computations per second.

**Fix pattern used for the Niuniu dashboard:**
1. Add in-process TTL JSON cache guarded by `threading.RLock` around expensive endpoints.
2. Emit cacheable headers for public read-only endpoints: `Cache-Control: public, max-age=<browser>, s-maxage=<edge>, stale-while-revalidate=<...>` plus `CDN-Cache-Control`, so Cloudflare absorbs most repeated public traffic.
3. Cap `/api/messages` payloads (`limit` default ~80, max ~200) and add `category` filtering so each tab fetches only its relevant records. Non-message tabs should request `limit=1` just for category counts/time, not full history.
4. Change frontend fetches to normal cacheable fetches (remove `{cache:'no-store'}`) and slow global refresh from 5s to ~15s. For heavy tabs, fetch only the endpoints they render.
5. Use short TTLs for trading/account state (3-5s), moderate TTLs for indexes/quotes (15-30s), and longer TTLs for sector/hot-stock/fund-flow helpers (60s). Keep mutating endpoints (`/trigger`, `/resume`) uncached and clear related cache keys after mutation.
6. Verify with two sequential requests per endpoint: first should be `X-Dashboard-Cache: MISS`, second should be `HIT` and millisecond-level. Then run a local concurrency smoke test against warmed endpoints (e.g. 300 requests, concurrency 80) and check p95 latency.

**Expected result from the June 2026 optimization:** warmed endpoints served ~2k-2.8k local req/s with p95 ~33ms, `/api/messages?limit=80&category=x_monitor` shrank to ~117KB, and `牛牛实战` tab fetched `/api/messages?limit=1`, `/api/b1_screen`, `/api/niuniu_practice`, `/api/practice_benchmarks` instead of the full message payload.

### 0.3 Slow tab switches from inline legacy sync

**Problem**: Clicking a dashboard tab can appear to hang for 10+ seconds even though the frontend uses SPA-style `event.preventDefault()` navigation. A common root cause is `/api/messages?limit=1` doing synchronous legacy log/cron sync (`merge_records(limit=None, include_origin=False)`) when its 60s interval expires. Because every tab switch first fetches `/api/messages`, the visible page does not change until that slow filesystem/log merge finishes.

**Fix pattern**:
1. Keep the fast path reading from SQLite (`push_history.query_messages`) synchronous.
2. Move legacy sync to a daemon background thread guarded by a lock / in-progress flag; only `force=True` maintenance calls should block.
3. In the frontend, update `activeCategory`, URL, tab active state, and render cached/placeholder content immediately in the click handler before awaiting fresh API data.
4. Abort stale in-flight `load()` requests with `AbortController` so rapid tab clicks do not render old responses over the newest tab.
5. Persist the latest view payload in `sessionStorage` for a short TTL (~30s) so returning to a tab feels instant while fresh data hydrates.

**Verification**:
```bash
python3 -m py_compile ~/.hermes/scripts/hermes_messages_dashboard.py
python3 - <<'PY'
from pathlib import Path
s=Path('~/.hermes/scripts/hermes_messages_dashboard.py').expanduser().read_text()
html=s.split('INDEX_HTML = r"""',1)[1].split('"""',1)[0]
Path('/tmp/dashboard.js').write_text(html.split('<script>',1)[1].split('</script>',1)[0])
PY
node --check /tmp/dashboard.js
curl -s -o /dev/null -w 'TTFB:%{time_starttransfer} TOTAL:%{time_total}\n' 'http://127.0.0.1:8787/api/messages?limit=1'
```
Expected after restart: `/api/messages?limit=1` cold TTFB should be tens of milliseconds, not seconds; browser click verification should show `.tab.active` and `location.href` switch immediately, with no console errors.

### 0.4 Public dashboard invite-gate / user management

**Problem**: When exposing a local/public dashboard through Cloudflare Tunnel, hiding the URL is not enough. Users can bypass the HTML shell and scrape `/api/*`, or abuse mutating endpoints like forced scans and resume-trading controls.

**Recommended pattern**: implement an application-layer invite-gate: `/login` redeems an invite code once, creates a per-viewer token, stores only its hash in SQLite, and sets an HttpOnly cookie. All normal routes and JSON APIs require a viewer token; sensitive/mutating endpoints require an admin token/role. Keep an admin UI at `/admin?token=<admin-token>` for creating invites, viewing users, disabling invites, and banning viewers. Use `DASHBOARD_MAX_ONLINE` + a short `last_seen_at` window for coarse online-count control.

**Protect these as admin-only**: `/api/b1_screen?force=1`, `/api/b1_screen/trigger`, `/api/niuniu_practice/resume`, `/api/self_optimize/apply`, plus all `/admin/*` and `/api/admin/*` routes.

**Verification**: unauthenticated `/` should redirect to `/login`; unauthenticated `/api/messages?limit=1` should return 401; invite login should set a cookie and allow read APIs; normal viewers should receive 403 for admin-only operations. See `references/dashboard-user-management-invite-gate.md` for schema, route contract, and smoke-test commands.

### 1. Tab Styling: Underline on Links

**Problem**: `.tab` elements rendered as `<a>` tags get browser-default `text-decoration: underline`.

**Fix**:
```css
.tab { text-decoration: none; display: inline-flex; align-items: center; }
.tab:visited, .tab:hover, .tab:active, .tab:focus { text-decoration: none; }
```

### 2. Empty Benchmark Data
**Problem**: API returns empty or stale data
**Solution**: Implement cache validation and fallback sources
```python
def validate_benchmark_data(data):
    if not data or len(data.get('points', [])) < 10:
        raise ValueError("Insufficient benchmark data")
    # Check if data is too old (>5 minutes)
    if time.time() - data.get('timestamp', 0) > 300:
        raise ValueError("Benchmark data too stale")
```

### 2. Chart Scaling Issues
**Problem**: Different scales make comparison meaningless
**Solution**: Normalize all data to percentage change from baseline
```javascript
function normalizeAllData(portfolioData, benchmarkData) {
  const portfolioPct = toPercentage(portfolioData, initialCash);
  const benchmarkPct = benchmarkData.map(b => 
    toPercentage(b.points, b.points[0]?.value || 100)
  );
  return { portfolioPct, benchmarkPct };
}
```

### 3. Mobile Responsiveness
**Problem**: Charts overflow on small screens
**Solution**: Dynamic viewBox and font scaling
```javascript
function getChartDimensions() {
  const width = window.innerWidth;
  if (width < 400) return { w: 400, h: 80, fontSize: 10 };
  if (width < 720) return { w: 600, h: 100, fontSize: 11 };
  return { w: 800, h: 120, fontSize: 12 };
}
```

## Integration with Trading Systems

### 1. Trading Simulator Integration
```python
# niuniu_practice_trader.py integration
def update_dashboard_with_trade(portfolio, trade):
    """Update dashboard after trade execution"""
    dashboard_data = {
        'equity_history': portfolio['equity_history'],
        'positions': portfolio['positions'],
        'cash': portfolio['cash'],
        'total_pnl': portfolio['total_pnl'],
        'decision_model': MODEL,
        'decision_provider': PROVIDER_DISPLAY_NAME
    }
    save_to_dashboard_cache(dashboard_data)
```

### 2. Real-time Updates
```javascript
// Auto-refresh every 5 seconds during trading hours
if (isTradingHours()) {
  setInterval(() => {
    if (document.visibilityState === 'visible') {
      refreshDashboardData();
    }
  }, 5000);
}
```

## Testing & Validation

### 1. Data Validation
```python
def test_benchmark_api():
    response = fetch('/api/practice_benchmarks')
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data
    assert len(data['items']) >= 4  # 上证, 沪深300, 创业板, 科创50
    for item in data['items']:
        assert 'points' in item
        assert len(item['points']) > 100  # Should have minute data
```

### 2. Visual Regression
```javascript
// Take screenshot of chart and compare with baseline
function test_chart_rendering() {
  const svg = document.querySelector('.practice-curve');
  const svgString = new XMLSerializer().serializeToString(svg);
  const hash = md5(svgString);
  assert.equal(hash, EXPECTED_HASH, 'Chart rendering changed');
}
```

## Deployment & Maintenance

### 2. Dashboard Index Page Full-Feature Restore

**Problem**: When recovering `hermes_messages_dashboard.py` from a backup, it is tempting to restore only the visible `/api/indices` cards. For this user, that is incomplete and considered broken: the `指数行情` tab must include A/H indexes, US overnight indexes, gold/FX/futures, industry indexes, and active stock rankings.

**Required sections**:
- `🇨🇳 A股 / 港股指数`: 上证指数、深证成指、创业板指、科创50、恒生指数
- `🌙 美股夜盘`: 道琼斯、纳斯达克、标普500
- `🥇 黄金 / 外汇 / 期货`: 富时A50、纽约黄金、现货黄金、美元人民币、美元指数
- `📊 板块涨幅`: 中证/上证行业指数
- `🔥 活跃股票榜`: 成交额前十、换手率前十、成交量前十

**Workflow correction**: Before declaring the page fixed, verify not just that index cards exist, but that the full section list exists. Use the detailed playbook in `references/indices-tab-full-restore.md`.

### 5. Restoring the Full `指数行情` Tab After Dashboard Rebuilds

**Problem**: Restoring `hermes_messages_dashboard.py` from an older backup can silently degrade the `指数行情` tab into a partial page. The user expects the full market overview, not only A-share index cards.

**Required sections for `指数行情`:**
- A股/港股指数: 上证、深证、创业板、科创50、恒生
- 美股夜盘: 道琼斯、纳斯达克、标普500
- 黄金/外汇/期货: 富时A50、纽约黄金、现货黄金、美元人民币、美元指数
- 板块涨跌幅: **涨幅前十 + 跌幅前十** red/green card grids
- 活跃股票榜: **成交额前十 + 换手率前十 + 成交量前十**
- 主力资金流向: **主力净流入前十 + 主力净流出前十** industry cards, amount in `亿`

**Do not “fix” the page by only restoring `/api/indices`**. That makes the page render but drops most of the user's expected dashboard.

**Known-good data-source pattern from the June 2026 repair session:**
- `/api/indices`: Tencent `qt.gtimg.cn` for A/HK/US indices; Sina `hq.sinajs.cn` for `hf_GC`, `hf_XAU`, `hf_CHA50CFD`, `USDCNY`, `DINIW`; Tencent `ifzq.gtimg.cn` for A-share sparklines.
- `/api/sectors`: combine `akshare.stock_fund_flow_industry(symbol="即时")` and `akshare.stock_fund_flow_concept(symbol="即时")`; sort to `gain_top` and `loss_top`; fallback to Tencent broad industry index codes only if akshare path fails.
- `/api/hot_stocks`: build a main-board universe with `akshare.stock_info_a_code_name()`, quote via Tencent `qt.gtimg.cn`, then sort `amount_top`, `turnover_top`, and `volume_top`.
- `/api/money_flow`: use `akshare.stock_fund_flow_industry(symbol="即时")`; return `inflow`/`outflow` sorted by `净额`, with `net_flow_yi` for display. Avoid blocked Eastmoney push2 fund-flow endpoints for this module.

**Visual requirement for mobile:** match the previous dark market-board style: three-column compact cards; red/dark-red for gain/net-inflow, green/dark-green for loss/net-outflow; active-stock and sector cards should share the same palette as main-fund-flow cards. Hide the `大盘资金流向` block when it is all zero so it does not distract from real `主力资金流向` data.

### 6. Dashboard Architecture (CRITICAL)

The dashboard script `hermes_messages_dashboard.py` relies on **5 helper API files** that live in the same directory. They are dynamically imported via `importlib.util` — the script does NOT inline the API logic:

| File | Function exported | Endpoint |
|---|---|---|
| `indices_dashboard_api.py` | `fetch_indices_data()` | `/api/indices` |
| `sectors_dashboard_api.py` | `fetch_sector_data()` | `/api/sectors` |
| `hot_stocks_dashboard_api.py` | `fetch_hot_stocks(sort_by)` | `/api/hot_stocks` |
| `money_flow_dashboard_api.py` | `fetch_money_flow()` | `/api/money_flow` |
| `market_flow_dashboard_api.py` | `fetch_market_flow()` | `/api/market_flow` |

**PITFALL**: If you rebuild the dashboard from a backup or copy, these helper files are NOT part of the main script. Each missing file causes its endpoint to return `{"error": "FileNotFoundError: ..."}` with empty data. The page renders but sections (板块, 热搜, 资金流) appear blank. **Always verify all 6 files are present** when restoring the dashboard.

### 2. Service Management
```bash
# Start dashboard service
python ~/.hermes/scripts/hermes_messages_dashboard.py

# Restart after changes
kill -HUP $(pgrep -f "hermes_messages_dashboard.py")

# Check status
curl -s http://127.0.0.1:8787/api/practice_benchmarks | jq '.items | length'
```

### 2. Index Dashboard Full-Market Contract

When repairing or refactoring the `指数行情` tab, preserve the full market overview. Do **not** simplify it down to four A-share index cards. The expected page includes A/H indices, US overnight indices, gold/FX/futures, sector gain/loss top ten, active stock rankings by amount/turnover/volume, and industry main-fund inflow/outflow top ten. See `references/index-dashboard-contract.md` for the concrete payload shapes, data sources, frontend rendering rules, and verification checklist.

### 3. Monitoring
- Check API response times (< 200ms)
- Validate data freshness (< 60 seconds)
- Monitor error rates in logs

## Reference Files

For detailed implementation patterns:
- `references/model-provider-switching.md`: Switching between LLM providers (OpenCode Zen, Crossdesk) for trading decisions
- `references/index-card-intraday-sparklines.md`: Repair notes for `指数行情` card sparklines — Tencent A-share minute data, Sina commodity minute lines (`伦敦金`, `布伦特原油指数`), and verification steps.
- `references/dashboard-index-page-restoration.md`: Full `指数行情` page architecture, helper API pitfalls, subprocess isolation for akshare-heavy helpers, and verification/style checks.
- `references/index-page-restoration.md`: Full `指数行情` page contract, visual palette, data sources, helper subprocess pattern, and verification checklist for preserving indices/global/gold/sector/fund-flow/active-stock modules.

## Related Skills

- `cn-stock-b1-screening`: For real-time A-share data and B1 screening
- `niuniu-practice-rules`: For trading simulator rules and constraints
- `hermes-agent`: For general Hermes configuration and deployment