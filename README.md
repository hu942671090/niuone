# 牛牛大作手 Dashboard · NiuOne

本仓库是牛牛大作手 Dashboard 的统一源码、运行和 Codex 维护目录。项目上传到 GitHub 后，会通过 `.github/workflows/ci.yml` 在 GitHub Actions 中执行同一套验证脚本。

- 项目根目录：克隆后的仓库目录
- 线上源码：`app/`
- 本机/线上运行数据：默认在工程目录内 `.local-data/runtime/`
- 启动入口：`run-dashboard.sh`
- 环境配置：默认读取工程目录内 `.local-data/dashboard.env`，可从 `dashboard.env.example` 复制后填写

## 目录结构

```text
.
├── .github/workflows/ci.yml # GitHub Actions 验证工作流
├── app/                    # 线上 dashboard Python 源码
│   ├── niuone_dashboard.py
│   ├── indices_dashboard_api.py
│   ├── sectors_dashboard_api.py
│   ├── hot_stocks_dashboard_api.py
│   ├── money_flow_dashboard_api.py
│   ├── market_flow_dashboard_api.py
│   ├── push_history.py
│   ├── niuniu_practice_trader.py
│   ├── us_rating_report.py
│   └── cn_stock_tools.py
├── tests/                  # 单测
├── docs/                   # 操作文档
├── scripts/                # validate / standalone / deploy 脚本
├── config/                 # 策略和运行说明
├── dashboard.env.example   # 可提交的环境变量样例
└── run-dashboard.sh        # 线上启动脚本
```

真实 DB、token、日志、缓存和本机虚拟环境已经移到仓库外：

```text
.local-data/
├── dashboard.env
├── runtime/
├── backups/
└── .venv/
```

## 快速开始

```bash
python3 -m pip install -r requirements.txt
./scripts/validate.sh
```

不创建 `dashboard.env` 也可以直接用默认值启动：

```bash
DASHBOARD_HOME=/tmp/niuone-smoke DASHBOARD_AUTH_ENABLED=0 DASHBOARD_PORT=8877 ./scripts/run_standalone.sh
```

生产或长期本地运行时，复制样例并把路径和密钥改成本机值：

```bash
mkdir -p .local-data
cp dashboard.env.example .local-data/dashboard.env
```

## Codex 维护流程

```bash
cd /path/to/NiuOne

# 1. 修改 app/ 下源码
# 例如：app/niuone_dashboard.py

# 2. 运行验证
./scripts/validate.sh

# 3. 本地临时启动副本，避免影响线上 8787
DASHBOARD_HOME=/tmp/niuone-smoke DASHBOARD_AUTH_ENABLED=*** DASHBOARD_PORT=8877 ./scripts/run_standalone.sh

# 4. 浏览器打开测试
# http://127.0.0.1:8877/

# 5. 确认无误后重启线上服务
./scripts/deploy_to_live.sh
```

## 验证命令

```bash
./scripts/validate.sh
```

会执行：

- 自动发现并执行 Python 语法检查
- 提取主 dashboard 内嵌 `<script>` 并执行 `node --check`
- 自动发现并执行 `tests/` 下的单测
- 自动发现并执行 Shell 脚本语法检查

## GitHub Actions

上传到 GitHub 后，`push`、`pull_request` 和手动触发都会运行：

```text
.github/workflows/ci.yml
```

CI 使用 Ubuntu runner、Python 3.13 和 Node.js 24，安装 `requirements.txt` 后执行：

```bash
./scripts/validate.sh
```

该工作流只验证源码和测试，不读取本机 `dashboard.env`，也不需要提交 `.local-data/` 中的数据库、token、日志或缓存。

## 独立任务入口

```bash
# 生成“每日美股机构买入评级汇报”，写入 $DASHBOARD_HOME/cron/output/fd0b807138f4 和 push_history.db
./scripts/run_us_rating_report.sh

# 增量迁移 Hermes 历史归档、状态和 push_history.db 记录到 NiuOne local-data runtime
python3 scripts/migrate_hermes_history.py
```

## 线上服务

线上监听：

```text
127.0.0.1:8787
```

LaunchAgent：

```text
~/Library/LaunchAgents/ai.niuone.dashboard.plist
~/Library/LaunchAgents/ai.niuone.cron-scheduler.plist
~/Library/LaunchAgents/ai.niuone.x-watchlist.plist
```

应指向：

```text
/path/to/NiuOne/run-dashboard.sh
```

## 关键文档

- `docs/OPERATIONS.md`：迁移、部署、验证、回滚完整操作手册
- `docs/STANDALONE.md`：独立运行说明
- `config/runtime-policy.md`：运行数据和 secrets 处理策略

## 不要提交/泄露

`.local-data/runtime/` 中包含真实运行数据和密钥：

- `dashboard_admin_token.txt`
- `dashboard_users.db`
- `push_history.db`
- `niuniu.db`
- `config.yaml`
- `cron/output/`
- `logs/`

这些都在 `.gitignore` 中，不要发给 Codex 外部上下文或公开仓库。
