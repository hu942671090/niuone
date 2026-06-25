# 牛牛实战页停留在“加载中…”的调试记录

## 场景

`https://stock.crossdesk.ccwu.cc/?category=b1_screen` 页面能打开外壳和 tab，但正文一直显示 `加载中…`。本地 dashboard、Cloudflare tunnel、相关 JSON API 均可返回 200。

## 关键症状

- `/` 和 `/?category=b1_screen` HTML 返回 200。
- `/api/b1_screen` 返回候选列表。
- `/api/niuniu_practice` 返回账户、持仓、权益曲线等数据。
- `/api/practice_benchmarks` 返回指数基准数据。
- 浏览器正文仍是 `加载中…`。
- 浏览器 console 中手动执行 `renderPracticePanel()` 得到：

```text
ReferenceError: Cannot access 'left' before initialization
    at renderPracticeCurve (...)
    at renderPracticePanel (...)
```

## 根因

两个前端问题叠加：

1. `renderPracticeCurve(history, dailyHistory, initialCash, benchmarks)` 的调用处只传了三个参数：

```js
renderPracticeCurve(p.equity_history || [], Number(p.initial_cash || 1000000), practiceBenchmarksData || {items:[]})
```

这会导致 `Number(initial_cash)` 被当成 `dailyHistory`，`practiceBenchmarksData` 被当成 `initialCash`。

2. `renderPracticeCurve` 的日期模式分支在创建 `xFromTime` 和 `timeTicks` 时引用 `left` / `innerW`，但这些 SVG 布局常量在分支之后才声明：

```js
xFromTime = time => {
  const idx = points.findIndex(p => p.time === time);
  if (idx < 0) return left; // left 尚未初始化
  return left + ... * innerW;
};
...
const w = 720, h = 210, left = 12, ...;
```

## 修复

调用处改为传入四个参数：

```js
renderPracticeCurve(
  p.equity_history || [],
  p.daily_equity_history || [],
  Number(p.initial_cash || 1000000),
  practiceBenchmarksData || {items:[]}
)
```

并把 SVG 布局常量提前到所有分支之前：

```js
const w = 720, h = 210, left = 12, right = 58, top = 18, bottom = 24;
const innerW = w - left - right, innerH = h - top - bottom;
const totalSessionMinutes = 4 * 60;
let points = [];
```

## 验证步骤

1. 语法检查：

```bash
python3 - <<'PY'
from pathlib import Path
s=Path('hermes_messages_dashboard.py').read_text()
html=s.split('INDEX_HTML = r"""',1)[1].split('"""',1)[0]
js=html.split('<script>',1)[1].split('</script>',1)[0]
Path('/tmp/dashboard.js').write_text(js)
PY
node --check /tmp/dashboard.js
python3 -m py_compile hermes_messages_dashboard.py
```

2. API 验证：

```bash
python3 - <<'PY'
import urllib.request,json
for u in ['http://127.0.0.1:8787/api/b1_screen','http://127.0.0.1:8787/api/niuniu_practice','http://127.0.0.1:8787/api/practice_benchmarks']:
    with urllib.request.urlopen(u, timeout=30) as r:
        d=json.loads(r.read().decode())
    print(u, list(d)[:8], len(d.get('items') or d.get('positions') or []), d.get('error') or d.get('last_error'))
PY
```

3. 浏览器验证：

- 打开 `https://stock.crossdesk.ccwu.cc/?category=b1_screen&t=<cache-buster>`。
- 等待 API 完成后检查 `#feed` 文本。
- 应看到：`牛牛实战 · 模拟账户`、初始资金/总权益/现金/累计收益、`收益曲线 · 实时净值`、持仓卡片、战法绩效、候选列表。

## 经验

当页面卡在 `加载中…` 但 API 全部正常时，不要继续只排 tunnel 或后端。优先用浏览器 console 执行页面渲染函数（如 `renderPracticePanel()` / `renderB1Screen()`），直接拿 runtime stack trace。