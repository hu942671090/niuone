# Dashboard 独立运行与迁移操作手册（给 Codex）

本文档记录「牛牛大作手 Dashboard」从 Hermes 目录迁出后的目录结构、开发/部署流程、启动方式、验证命令和回滚方案。Codex 后续维护 dashboard 时，请优先阅读本文件。

## 1. 当前线上架构

Dashboard 已从 Hermes 运行目录迁出，当前独立目录为：

```text
/path/to/NiuOne/
```

目录结构：

```text
/path/to/NiuOne/
├── app/                 # 线上 dashboard 源码
├── runtime/             # 线上 dashboard 运行数据
├── dashboard.env        # 线上启动环境变量
├── run-dashboard.sh     # 线上独立启动入口
└── MIGRATION_INFO.txt   # 最近一次迁移信息
```

### 1.1 线上源码目录

```text
/path/to/NiuOne/app/
```

关键文件：

| 文件 | 作用 |
|---|---|
| `niuone_dashboard.py` | Dashboard HTTP 服务、HTML/CSS/JS、API、用户系统 |
| `push_history.py` | 消息历史 SQLite 存取 |
| `niuniu_practice_trader.py` | 牛牛实战模拟账户/交易逻辑 |
| `indices_dashboard_api.py` | 指数行情 helper |
| `sectors_dashboard_api.py` | 板块涨跌幅 helper |
| `hot_stocks_dashboard_api.py` | 活跃股票榜 helper |
| `money_flow_dashboard_api.py` | 主力资金流 helper |
| `market_flow_dashboard_api.py` | 大盘资金流 helper |
| `cn_stock_tools.py` | A股行情工具，供 practice trader fallback 使用 |

### 1.2 线上运行数据目录

```text
/path/to/NiuOne/.local-data/runtime/
```

关键文件：

| 文件 | 作用 | 是否应提交给 Codex/Git |
|---|---|---|
| `dashboard_users.db` | 邀请码 / viewer / admin 用户 DB | 否 |
| `dashboard_admin_token.txt` | 管理员 token | 否 |
| `push_history.db` | Dashboard 消息历史 DB | 否 |
| `niuniu.db` | 牛牛实战运行数据 | 否 |
| `config.yaml` | provider/model/API 配置 | 否 |
| `cron/output/` | B1 缓存、模拟账户状态、helper cache | 否 |
| `logs/` | dashboard stdout/stderr | 否 |

> 重要：运行数据和 token 不应复制到 Codex 上下文、Git、公开目录或文档中。

## 2. Codex 开发工作区

Codex 应在这个目录里开发：

```text
/path/to/NiuOne/
```

结构：

```text
/path/to/NiuOne/
├── app/                 # 源码副本，Codex 修改这里
├── tests/               # 测试
├── docs/                # 文档
├── scripts/             # validate / deploy / standalone runner
├── config/              # 运行策略说明
├── fixtures/            # 样例数据，不放真实 DB/token
├── README.md
└── MANIFEST.json
```

Codex 的默认流程：

```bash
cd /path/to/NiuOne

# 修改 app/ 下源码

# 验证
./scripts/validate.sh

# 本地独立启动测试，不影响线上 8787
DASHBOARD_HOME=$PWD/runtime DASHBOARD_PORT=8877 ./scripts/run_standalone.sh
```

访问测试实例：

```text
http://127.0.0.1:8877/
```

## 3. 环境变量契约

Dashboard 现在使用 `DASHBOARD_HOME` 作为独立运行根目录。

| 变量 | 线上值/默认值 | 说明 |
|---|---|---|
| `DASHBOARD_HOME` | `/path/to/NiuOne/.local-data/runtime` | dashboard 运行数据根目录 |
| `DASHBOARD_TRADER_SCRIPT` | `/path/to/NiuOne/app/niuniu_practice_trader.py` | 牛牛实战模块路径 |
| `DASHBOARD_PORTFOLIO_STATE` | `$DASHBOARD_HOME/cron/output/niuniu_practice_portfolio.json` | 模拟账户状态文件 |
| `DASHBOARD_CONFIG` | `$DASHBOARD_HOME/config.yaml` | provider/model 配置 |
| `DASHBOARD_PUSH_HISTORY_DB` | `$DASHBOARD_HOME/push_history.db` | 消息历史 DB，可选显式设置 |
| `DASHBOARD_B1_SCANNER` | 可选 | B1 扫描脚本路径；缺失时 trigger 会返回错误但页面可运行 |
| `DASHBOARD_AUTH_ENABLED` | `1` | 是否启用邀请码登录 |
| `DASHBOARD_MAX_ONLINE` | `0` | 最大在线 viewer，0 表示不限制 |
| `DASHBOARD_ONLINE_WINDOW_SECONDS` | `300` | 在线判断窗口 |
| `DASHBOARD_AUTH_TOUCH_INTERVAL_SECONDS` | `30` | 同一 token 更新在线状态的最小间隔，降低公网轮询写库压力 |
| `DASHBOARD_TRUSTED_PROXIES` | `127.0.0.1/32,::1/128` | 允许信任 `CF-Connecting-IP` / `X-Forwarded-*` 的代理 CIDR；公网直连时不要放宽 |
| `DASHBOARD_RATE_LIMIT_ENABLED` | `1` | 是否启用 dashboard 内置 IP/token 限流 |
| `DASHBOARD_RATE_LIMIT_ANON` | `240` | 未登录同 IP 每分钟请求上限 |
| `DASHBOARD_RATE_LIMIT_AUTH` | `900` | 已登录同 token 每分钟 API 请求上限 |
| `DASHBOARD_RATE_LIMIT_LOGIN` | `20` | 同 IP 每分钟登录尝试上限 |
| `DASHBOARD_RATE_LIMIT_ADMIN` | `90` | 同 IP 每分钟管理/强制刷新操作上限 |
| `DASHBOARD_EDGE_CACHE_ENABLED` | `0` | 是否允许 CDN 缓存 API；公网带用户数据时保持 `0` |
| `DASHBOARD_API_CACHE_MAX_ENTRIES` | `256` | 进程内 API 响应缓存条目上限 |
| `DASHBOARD_API_OFFSET_MAX` | `5000` | 消息历史分页最大 offset，避免超深分页拖慢服务 |

兼容性：

- 新部署应使用 `DASHBOARD_HOME`。
- 源码 helper 应使用 `SCRIPT_DIR = Path(__file__).resolve().parent` 找旁边文件。

## 4. 验证流程

### 4.1 工作区验证

```bash
cd /path/to/NiuOne
./scripts/validate.sh
```

该脚本执行：

1. Python 语法检查
2. 提取 `niuone_dashboard.py` 内嵌 `<script>` 后运行 `node --check`
3. 用户系统单测：`tests/test_dashboard_auth.py`
4. 独立路径单测：`tests/test_standalone_paths.py`

预期输出：

```text
== Python syntax checks ==
== Embedded dashboard JavaScript syntax ==
== Unit tests ==
OK
== OK ==
```

### 4.2 临时独立实例验证

```bash
cd /path/to/NiuOne
DASHBOARD_HOME=/tmp/niuniu-dashboard-smoke DASHBOARD_AUTH_ENABLED=0 DASHBOARD_PORT=8878 ./scripts/run_standalone.sh
```

另一个终端检查：

```bash
curl -s -o /dev/null -w 'HTTP:%{http_code} TOTAL:%{time_total}\n' http://127.0.0.1:8878/
curl -s -o /dev/null -w 'HTTP:%{http_code} TOTAL:%{time_total}\n' http://127.0.0.1:8878/api/auth/status
```

预期：

```text
HTTP:200
HTTP:200
```

### 4.3 线上服务验证

线上监听：

```text
127.0.0.1:8787
```

检查：

```bash
curl -s -o /dev/null -w 'LOGIN HTTP:%{http_code} TOTAL:%{time_total}\n' http://127.0.0.1:8787/login
```

需要 admin token 时：

```bash
TOKEN=$(cat /path/to/NiuOne/.local-data/runtime/dashboard_admin_token.txt)

curl -s "http://127.0.0.1:8787/api/auth/status?token=$TOKEN"
curl -s "http://127.0.0.1:8787/api/messages?limit=1&token=$TOKEN" | python3 -m json.tool | head
curl -s "http://127.0.0.1:8787/api/b1_screen?token=$TOKEN" | python3 -m json.tool | head
curl -s "http://127.0.0.1:8787/api/niuniu_practice?token=$TOKEN" | python3 -m json.tool | head
```

关键检查：`/api/messages` 返回里的 `db_path` 应该是：

```text
/path/to/NiuOne/.local-data/runtime/push_history.db
```

不应该是：

```text
~/.hermes/push_history.db
```

### 4.4 公网 / Cloudflare Tunnel 检查

Dashboard 通过 Cloudflare Tunnel 开放到公网时，必须保持：

- `dashboard.env` 中 `DASHBOARD_AUTH_ENABLED=1`。
- `DASHBOARD_EDGE_CACHE_ENABLED=0`，避免 CDN 缓存带权限的数据接口。
- 默认只信任本机代理提供的 `CF-Connecting-IP` / `X-Forwarded-*`；如反向代理不在本机，先设置 `DASHBOARD_TRUSTED_PROXIES` 为代理出口 CIDR。
- 强制扫描、恢复交易、自优化应用等变更接口必须使用 `POST`，并带 `X-NiuOne-Action: 1` 请求头。
- Cloudflare Tunnel 只回源 `http://127.0.0.1:8787`，不要把 dashboard 直接监听到公网网卡。
- Cloudflare 建议开启 WAF / Bot Fight Mode / Rate Limiting，并对 `/login`、`/api/` 设置更严格规则。
- 公网分享优先使用邀请码，不直接分享 `?token=` 链接；如必须临时使用 admin token 链接，首次打开后服务会写入 HttpOnly cookie 并跳转到无 token URL。

快速健康检查：

```bash
curl -I http://127.0.0.1:8787/login
curl -I http://127.0.0.1:8787/
curl -I 'http://127.0.0.1:8787/api/messages?limit=1'
```

预期：

- `/login` 返回 `200`，带 `X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff`、`Content-Security-Policy`。
- `/` 未登录返回 `303` 到 `/login`。
- `/api/messages?limit=1` 未登录返回 `401`。

## 5. 部署流程：从 Codex 工作区发布到线上独立 app

推荐使用脚本：

```bash
cd /path/to/NiuOne
./scripts/validate.sh
```

`app/` 就是线上源码目录。验证通过后无需再从其它目录同步；如果 Codex 已经直接修改 `app/`，只需要重启线上 dashboard：

```bash
cd /path/to/NiuOne
./scripts/deploy_to_live.sh
```

如需先备份当前线上源码：

```bash
mkdir -p /path/to/NiuOne/.local-data/backups/manual-$(date +%Y%m%d-%H%M%S)
rsync -a /path/to/NiuOne/app/ /path/to/NiuOne/.local-data/backups/manual-$(date +%Y%m%d-%H%M%S)/app/
```

重启线上 dashboard：

```bash
launchctl kickstart -k gui/$(id -u)/ai.niuone.dashboard
```

然后执行「4.3 线上服务验证」。

## 6. LaunchAgent 状态

LaunchAgent 文件：

```text
~/Library/LaunchAgents/ai.niuone.dashboard.plist
~/Library/LaunchAgents/ai.niuone.cron-scheduler.plist
~/Library/LaunchAgents/ai.niuone.x-watchlist.plist
```

当前已经指向独立启动入口：

```text
/path/to/NiuOne/run-dashboard.sh
/path/to/NiuOne/run-niuone-cron-scheduler.sh
/path/to/NiuOne/run-x-watchlist-daemon.sh
```

查看：

```bash
launchctl print gui/$(id -u)/ai.niuone.dashboard | sed -n '1,100p'
launchctl print gui/$(id -u)/ai.niuone.cron-scheduler | sed -n '1,100p'
launchctl print gui/$(id -u)/ai.niuone.x-watchlist | sed -n '1,100p'
```

## 7. 回滚流程

迁移备份位置记录在：

```text
/path/to/NiuOne/.local-data/MIGRATION_INFO.txt
```

旧部署备份：

```text
~/Library/LaunchAgents/disabled-legacy-*
```

推荐回滚到最近 NiuOne 备份，然后重启：

```bash
cd /path/to/NiuOne
./scripts/validate.sh
launchctl kickstart -k gui/$(id -u)/ai.niuone.dashboard
```

回滚验证：

```bash
curl -s -o /dev/null -w 'HTTP:%{http_code}\n' http://127.0.0.1:8787/login
```

## 8. 常见坑

### 9.1 `push_history.db` 仍指向 `~/.hermes`

现象：

```json
"db_path": "~/.hermes/push_history.db"
```

修复：

- 确保 `DASHBOARD_HOME` 已设置。
- 确保 `DASHBOARD_PUSH_HISTORY_DB` 指向 `$DASHBOARD_HOME/push_history.db`，或 `push_history.py` 已支持 `DASHBOARD_HOME`。
- 如果通过 legacy shim 启动，确保 shim 里有：

```python
sys.path.insert(0, str(APP))
os.environ.setdefault("DASHBOARD_PUSH_HISTORY_DB", str(RUNTIME / "push_history.db"))
```

### 9.2 helper cache 写回 `~/.hermes/cron/output`

检查这些文件：

- `sectors_dashboard_api.py`
- `hot_stocks_dashboard_api.py`
- `money_flow_dashboard_api.py`

cache 应基于：

```python
os.environ.get("DASHBOARD_HOME") or PROJECT_ROOT / "runtime"
```

### 9.3 修改内嵌 JS 后页面空白

运行：

```bash
cd /path/to/NiuOne
./scripts/validate.sh
```

它会执行 `node --check` 检查内嵌 JS。

### 9.4 不要把真实 token/DB 交给 Codex

Codex 可以读源码和文档，但不要复制：

- `runtime/dashboard_admin_token.txt`
- `runtime/dashboard_users.db`
- `runtime/push_history.db`
- `runtime/niuniu.db`
- `runtime/config.yaml`

## 10. 给 Codex 的维护原则

1. 只改 `/path/to/NiuOne/app/`。
2. 每次改动后运行 `./scripts/validate.sh`。
3. 临时测试用独立 `DASHBOARD_HOME=/tmp/...` 和非 8787 端口。
4. 部署前备份线上 `/path/to/NiuOne/app/`。
5. 部署后验证 `db_path` 是否仍在 `/path/to/NiuOne/.local-data/runtime/`。
6. 不要重新引入 `~/.hermes` 硬编码路径。
