# Runtime / Secrets Policy

本目录是 NiuOne Dashboard 的统一目录：

```text
/path/to/NiuOne
```

真实运行数据默认在工程目录内的忽略目录：

```text
.local-data/runtime/
```

## 不应提交/外传的文件

| 文件 | 说明 |
|---|---|
| `.local-data/runtime/dashboard_admin_token.txt` | 管理员 token |
| `.local-data/runtime/dashboard_users.db` | 邀请码和 viewer 数据库 |
| `.local-data/runtime/push_history.db` | dashboard 消息历史 |
| `.local-data/runtime/niuniu.db` | 牛牛实战交易/账户数据 |
| `.local-data/runtime/config.yaml` | provider/API 配置 |
| `.local-data/runtime/cron/output/` | B1/cache/helper 输出 |
| `.local-data/runtime/logs/` | 服务日志 |

## 本地副本测试建议

不要直接拿真实 `.local-data/runtime/` 做实验。测试时使用临时 `DASHBOARD_HOME`：

```bash
cd /path/to/NiuOne
DASHBOARD_HOME=/tmp/niuone-smoke DASHBOARD_AUTH_ENABLED=*** DASHBOARD_PORT=8877 ./scripts/run_standalone.sh
```

如果需要测试鉴权，使用测试里的临时 DB 模式：

```bash
./scripts/validate.sh
```

## 线上启动

线上服务使用：

```bash
/path/to/NiuOne/run-dashboard.sh
```

环境变量在：

```text
.local-data/dashboard.env
```
