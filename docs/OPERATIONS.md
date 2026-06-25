# NiuOne 运行与维护手册

本文档记录 NiuOne Dashboard 的本地运行、验证、部署、日志和回滚流程。真实运行数据统一放在工程目录内 `.local-data/`，该目录不进入 Git。

## 1. 目录约定

```text
/path/to/NiuOne/
├── app/                    # Dashboard 和任务源码
├── tests/                  # 单元测试
├── scripts/                # 验证、部署和独立任务脚本
├── docs/                   # 文档
├── config/                 # 运行策略说明
├── .local-data/            # 本机真实运行数据，Git ignored
├── run.sh                  # macOS/Linux 一键启动
├── run.command             # macOS 双击启动
├── run.bat                 # Windows 双击启动
├── run.ps1                 # Windows PowerShell 启动
├── run.desktop             # Linux 桌面启动
└── run-dashboard.sh        # 生产/LaunchAgent 启动入口
```

运行数据默认位于：

```text
.local-data/
├── dashboard.env
├── .venv/
├── runtime/
│   ├── dashboard_users.db
│   ├── dashboard_admin_token.txt
│   ├── push_history.db
│   ├── niuniu.db
│   ├── config.yaml
│   ├── cron/output/
│   └── logs/
└── backups/
```

不要把 `.local-data/` 中的 DB、token、日志、模型配置或归档内容提交到 Git，也不要复制到公开上下文。

## 2. 一键运行

| 系统 | 启动方式 |
|---|---|
| macOS | 双击 `run.command`，或终端执行 `./run.sh` |
| Windows | 双击 `run.bat`，或 PowerShell 执行 `.\run.ps1` |
| Linux | 终端执行 `./run.sh`，桌面环境可尝试双击 `run.desktop` |

首次运行会自动创建 `.local-data/.venv`、安装依赖、生成 `.local-data/dashboard.env`，并启动：

```text
http://127.0.0.1:8787/
```

Linux 如提示没有执行权限：

```bash
chmod +x run.sh run.desktop
```

## 3. 关键环境变量

配置文件默认读取：

```text
.local-data/dashboard.env
```

| 变量 | 默认 | 说明 |
|---|---|---|
| `DASHBOARD_HOME` | `.local-data/runtime` | 运行数据根目录 |
| `DASHBOARD_HOST` | `127.0.0.1` | Dashboard 监听地址 |
| `DASHBOARD_PORT` | `8787` | Dashboard 监听端口 |
| `PYTHON_BIN` | `.local-data/.venv/bin/python` 或 Windows venv Python | Python 可执行文件 |
| `DASHBOARD_CONFIG` | `$DASHBOARD_HOME/config.yaml` | provider/model 配置 |
| `DASHBOARD_PUSH_HISTORY_DB` | `$DASHBOARD_HOME/push_history.db` | 消息历史 DB |
| `DASHBOARD_PORTFOLIO_STATE` | `$DASHBOARD_HOME/cron/output/niuniu_practice_portfolio.json` | 模拟账户状态 |
| `DASHBOARD_TRADER_SCRIPT` | `app/niuniu_practice_trader.py` | 牛牛实战脚本 |
| `DASHBOARD_AUTH_ENABLED` | 一键本地启动默认 `0` | 公网或多人访问必须设置为 `1` |
| `DASHBOARD_ADMIN_PASSWORD` | 空 | 管理页密码，可留空使用 admin token |
| `DASHBOARD_TRUSTED_PROXIES` | `127.0.0.1/32,::1/128` | 允许信任转发 IP 的代理 CIDR |
| `DASHBOARD_EDGE_CACHE_ENABLED` | `0` | 是否允许 CDN 缓存 API |

公网或局域网访问前，至少确认：

- `DASHBOARD_AUTH_ENABLED=1`
- `DASHBOARD_HOST` 没有误暴露到不可信网络
- `DASHBOARD_EDGE_CACHE_ENABLED=0`
- `DASHBOARD_TRUSTED_PROXIES` 只包含可信反向代理

## 4. 验证流程

```bash
./scripts/validate.sh
```

验证内容：

1. Python 语法检查
2. Dashboard 内嵌 JavaScript `node --check`
3. Shell 启动脚本语法检查
4. PowerShell 脚本语法检查（环境存在 PowerShell 时）
5. `tests/` 单元测试

临时启动隔离实例：

```bash
DASHBOARD_HOME=/tmp/niuone-smoke DASHBOARD_AUTH_ENABLED=0 DASHBOARD_PORT=8878 ./scripts/run_standalone.sh
```

健康检查：

```bash
curl -s -o /dev/null -w 'HTTP:%{http_code} TOTAL:%{time_total}\n' http://127.0.0.1:8878/
curl -s -o /dev/null -w 'HTTP:%{http_code} TOTAL:%{time_total}\n' http://127.0.0.1:8878/api/auth/status
```

预期均返回 `HTTP:200`。

## 5. 本机长期运行

macOS LaunchAgent 文件：

```text
~/Library/LaunchAgents/ai.niuone.dashboard.plist
~/Library/LaunchAgents/ai.niuone.cron-scheduler.plist
~/Library/LaunchAgents/ai.niuone.x-watchlist.plist
```

它们应分别调用：

```text
/path/to/NiuOne/run-dashboard.sh
/path/to/NiuOne/run-niuone-cron-scheduler.sh
/path/to/NiuOne/run-x-watchlist-daemon.sh
```

查看状态：

```bash
launchctl print gui/$(id -u)/ai.niuone.dashboard | sed -n '1,100p'
launchctl print gui/$(id -u)/ai.niuone.cron-scheduler | sed -n '1,100p'
launchctl print gui/$(id -u)/ai.niuone.x-watchlist | sed -n '1,100p'
```

重启：

```bash
launchctl kickstart -k gui/$(id -u)/ai.niuone.dashboard
launchctl kickstart -k gui/$(id -u)/ai.niuone.cron-scheduler
launchctl kickstart -k gui/$(id -u)/ai.niuone.x-watchlist
```

## 6. 部署流程

```bash
cd /path/to/NiuOne
./scripts/validate.sh
./scripts/deploy_to_live.sh
```

`deploy_to_live.sh` 会备份当前 `app/` 到 `.local-data/backups/`，然后重启本机 LaunchAgent 服务。

部署后检查：

```bash
curl -s -o /dev/null -w 'LOGIN HTTP:%{http_code} TOTAL:%{time_total}\n' http://127.0.0.1:8787/login
TOKEN=$(cat .local-data/runtime/dashboard_admin_token.txt)
curl -s "http://127.0.0.1:8787/api/messages?limit=1&token=$TOKEN" | python3 -m json.tool | head
```

`/api/messages` 返回中的 `db_path` 应指向：

```text
/path/to/NiuOne/.local-data/runtime/push_history.db
```

## 7. 常用任务

```bash
# 生成美股机构买入评级日报，并写入 Dashboard 归档和消息库
./scripts/run_us_rating_report.sh

# 运行 cron scheduler
./run-niuone-cron-scheduler.sh

# 运行 X 关注列表监控 daemon
./run-x-watchlist-daemon.sh
```

## 8. 回滚

备份默认位于：

```text
.local-data/backups/
```

手动回滚示例：

```bash
cp -R .local-data/backups/<backup-name>/app/. app/
./scripts/validate.sh
launchctl kickstart -k gui/$(id -u)/ai.niuone.dashboard
```

回滚后检查：

```bash
curl -s -o /dev/null -w 'HTTP:%{http_code}\n' http://127.0.0.1:8787/login
```

## 9. 常见问题

### Dashboard 无法启动

检查：

```bash
./run.sh --no-browser
```

确认 Python 可用、依赖安装成功、`DASHBOARD_PORT` 未被占用。

### 页面能打开但没有历史消息

检查消息库：

```bash
ls -lh .local-data/runtime/push_history.db
TOKEN=$(cat .local-data/runtime/dashboard_admin_token.txt)
curl -s "http://127.0.0.1:8787/api/messages?limit=5&token=$TOKEN" | python3 -m json.tool | head
```

当前消息流以 `push_history.db` 为唯一来源。任务脚本需要正常写入该 DB 后，Dashboard 才会出现对应消息。

### 修改前端后页面空白

运行：

```bash
./scripts/validate.sh
```

该脚本会抽取 `app/niuone_dashboard.py` 内嵌 JavaScript 并执行 `node --check`。

### 不要提交真实数据

提交前检查：

```bash
git status --ignored --short
```

`.local-data/` 应显示为 ignored，不应出现在 staged files 中。

## 10. 维护原则

1. 改动源码后运行 `./scripts/validate.sh`。
2. 临时测试使用独立 `DASHBOARD_HOME=/tmp/...` 和非 8787 端口。
3. 公网访问必须开启认证和限流。
4. 真实 DB、token、日志、模型配置只留在 `.local-data/`。
5. 新任务应直接写入 `push_history.db` 或 Dashboard 当前归档目录。
