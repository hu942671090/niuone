# app 模块结构

`app/` 根目录不再放业务实现或零散入口。受支持的命令行/服务入口集中在 `app/entrypoints/`，历史裸模块适配器集中在 `app/compat/`，其余子包承载领域实现。兼容适配器由 `_compat.py` 在历史模块命名空间中执行迁移后的实现，因此运行时 monkeypatch 语义保持不变。

## 领域边界

| 目录 | 职责 | 不应承担的职责 |
|---|---|---|
| `app/core/` | 运行路径策略、原子 JSON 缓存等跨领域基础设施 | 业务规则、服务编排 |
| `app/automation/` | 定时任务模型、Cron 匹配与时间配置规则 | 信号处理、子进程执行和调度器状态 |
| `app/dashboard/` | 看板请求解析、安全辅助、API 缓存编排和榜单规则 | HTTP 路由编排、进程级可变状态 |
| `app/market_data/` | 行情访问和证券代码规范化工具 | 策略决策、交易状态 |
| `app/messaging/` | 通知模型、渠道适配、HTTP 传输、分发和成交消息格式 | 交易状态持久化 |
| `app/monitoring/x/` | X 关注列表、媒体/上下文解析、消息格式、时间与重试状态规则 | 网络抓取、进程循环和消息入库 |
| `app/reports/a_share/` | A 股报告共用的数值、代码、行业、日历、Grok 提示词/解析和超时工具 | 定时任务入口、数据源编排 |
| `app/storage/` | 报告记录构造、消息 ID/去重规则和显式存储接口 | 数据库路径和进程级连接状态 |
| `app/screening/` | 多策略扫描和候选行业增强 | 账户执行、HTTP 路由 |
| `app/strategies/` | 策略注册、评分、归因、选股、退出规则和提示词片段 | 行情 I/O、账户执行 |
| `app/trading/` | 模拟交易中的纯计算能力，例如卖出技术信号 | 账户文件、网络请求和成交落盘 |

`entrypoints/` 中的 Dashboard、交易器、调度器、监控器和报告入口均为薄启动器；`compat/` 中的各 `*_dashboard_api.py`、`notifications.py` 及历史模块名均为薄适配器。实际组合实现分别位于 `dashboard/server.py`、`trading/practice_trader.py`、`automation/scheduler_service.py`、各领域的 `*_service.py` 等文件。

组合层的正式执行合同是直接运行 `app/entrypoints/*.py`。领域实现使用 `app.<domain>` 包路径；仍依赖历史裸模块名的组合代码由入口统一加载 `app/compat/`，外部代码不应再依赖已经移除的 `app/*.py` 路径。

## 依赖方向

```text
启动脚本 / 兼容入口
        ↓
领域包（core、automation、dashboard、messaging、monitoring、reports、storage、strategies、trading）
        ↓
标准库与外部数据源
```

领域包不能反向导入根入口。进程锁、缓存、文件路径、运行时配置等可变状态由组合层持有；领域函数优先接收显式参数。这样既能独立测试，又能保留调用方对旧模块全局值进行替换的兼容行为。

## 变更检查

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
./scripts/validate.sh
```

新增功能应优先放入对应领域包；只有 CLI、HTTP 路由、调度或跨域编排代码留在根入口。
