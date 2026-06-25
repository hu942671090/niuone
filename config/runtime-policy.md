# 运行数据和 secrets 处理策略

本文档定义 NiuOne 的运行数据、模型密钥和本地私有文件处理规则。目标是让真实数据可以留在工程目录内，同时确保上传 GitHub 的内容不包含用户数据或 secrets。

## 目录边界

源码目录：

```text
/path/to/NiuOne
```

私有运行目录：

```text
.local-data/
├── dashboard.env
├── .venv/
├── runtime/
└── backups/
```

`.local-data/`、`dashboard.env`、数据库、token、日志和备份文件都已在 `.gitignore` 中忽略。

## 不应提交或外传的内容

| 路径 | 说明 |
|---|---|
| `.local-data/dashboard.env` | 本机环境变量、路径和可能存在的 secrets |
| `.local-data/.venv/` | 本机 Python 虚拟环境 |
| `.local-data/runtime/dashboard_admin_token.txt` | 管理员 token |
| `.local-data/runtime/dashboard_users.db` | 邀请码和 viewer 数据库 |
| `.local-data/runtime/push_history.db` | 消息历史 |
| `.local-data/runtime/niuniu.db` | 牛牛实战交易和账户数据 |
| `.local-data/runtime/config.yaml` | provider、模型和 API key 配置 |
| `.local-data/runtime/cron/state/` | 定时任务、X 监控和补跑状态 |
| `.local-data/runtime/cron/output/` | B1、市场监控、美股评级、X 监控等任务输出 |
| `.local-data/runtime/logs/` | 服务和任务日志 |
| `.local-data/backups/` | 部署备份，可能包含旧配置 |

不要把上述内容复制到 issue、PR、README、文档示例或聊天上下文。排查问题时只提供脱敏后的错误类型、时间点和必要字段。

## 模型密钥

推荐用途：

| 用途 | 推荐模型 | 配置项 |
|---|---|---|
| 事件抓取、信息检索、X 关注列表监控、美股机构评级日报 | Grok | `DASHBOARD_GROK_BASE_URL`、`DASHBOARD_GROK_API_KEY`、`DASHBOARD_GROK_MODEL` |
| 选股后的买卖决策 | DeepSeek | `DASHBOARD_DECISION_BASE_URL`、`DASHBOARD_DECISION_API_KEY`、`DASHBOARD_DECISION_MODEL` |

API key 只允许保存在 `.local-data/dashboard.env`、`.local-data/runtime/config.yaml` 或受控的系统环境变量中。提交前必须确认没有新增 `.env`、`*.key`、`*.token`、`*.secret`、数据库或备份文件。

## 本地副本和测试

不要直接拿真实 `.local-data/runtime/` 做实验。测试时使用临时运行目录：

```bash
DASHBOARD_HOME=/tmp/niuone-smoke DASHBOARD_AUTH_ENABLED=0 DASHBOARD_PORT=8877 ./scripts/run_standalone.sh
```

提交前运行：

```bash
./scripts/validate.sh
git status --ignored --short
```

`.local-data/` 应显示为 ignored，不应出现在 staged files 中。

## 发布和备份

本机部署脚本会把当前 `app/`、环境文件和启动脚本备份到：

```text
.local-data/backups/
```

备份目录同样属于私有数据区域，不应提交或外传。回滚时优先从备份恢复 `app/`，或使用 `git revert` 做非破坏性提交回滚。

## 处理疑似泄露

如果 API key、token 或数据库误入公开位置：

1. 立即撤销或轮换对应 key/token。
2. 从代码和文档中删除泄露内容。
3. 检查 `git status --ignored --short` 和最近提交。
4. 必要时重建 `.local-data/runtime/dashboard_admin_token.txt`、邀请码和相关数据库。
5. 对已经推送到远端的敏感内容，按远端平台的泄露处理流程清理历史。
