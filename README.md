# NiuOne · 牛牛1号

[![CI](https://github.com/kunkundi/niuone/actions/workflows/ci.yml/badge.svg)](https://github.com/kunkundi/niuone/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

NiuOne 是一个本地优先的市场信息与交易辅助工具。它把 A 股市场面板、策略筛选、模拟交易、X 关注列表监控、美股机构评级摘要和定时任务归档集中在同一个轻量 Python 服务中。

项目默认将所有运行数据、数据库、日志、token 和本地虚拟环境写入 `.local-data/`。该目录已被 `.gitignore` 忽略，适合把源码公开到 GitHub，同时把真实数据保留在工程目录内。

> NiuOne 仅用于研究、信息整理和个人决策辅助，不构成任何投资建议。

## 功能概览

- **一键本地运行**：macOS、Windows、Linux 均提供命令行启动入口，首次运行自动创建虚拟环境并安装依赖。
- **聚合视图**：展示消息历史、指数、板块、热门股票、资金流、市场流向和策略结果。
- **策略与模拟交易**：集成 B1 策略扫描、内置策略/预设文字策略二选一、牛牛实战模拟账户、持仓和收益曲线展示。
- **定时任务归档**：支持市场监控、美股机构评级日报、X 关注列表监控等任务输出。
- **本地访问控制**：支持邀请码、管理员 token、管理员密码、限流和运行配置管理。

## 系统要求

通用要求：

| 依赖 | 用途 |
|---|---|
| Python 3.11+ | 运行本地服务、创建虚拟环境、执行任务脚本 |
| Git | 克隆项目 |

平台相关：

| 平台 | 运行方式 |
|---|---|
| macOS / Linux | 执行 `./run.sh` |
| Windows | 使用 PowerShell 执行 `run.ps1` |

Python 依赖由一键启动脚本自动安装，当前核心依赖见 [requirements.txt](requirements.txt)。

## 快速开始

```bash
git clone https://github.com/kunkundi/niuone.git
cd niuone
```

| 系统 | 启动方式 |
|---|---|
| macOS | 终端执行 `./run.sh` |
| Windows | PowerShell 执行 `.\run.ps1` |
| Linux | 终端执行 `./run.sh` |

本地一键启动默认关闭访问认证，且管理员密码为空；此时本机访问 `/admin` 不需要额外密码。长期运行、多人使用或暴露到非本机网络前，建议启动时设置管理员密码：

```bash
./run.sh --admin-password "change-this-to-a-strong-password"
```

Windows PowerShell：

```powershell
.\run.ps1 --admin-password "change-this-to-a-strong-password"
```

启动后浏览器会自动打开：

```text
http://127.0.0.1:8787/
```

首次运行会自动完成：

- 创建 `.local-data/`
- 创建 `.local-data/.venv`
- 安装 `requirements.txt`
- 生成本地配置文件
- 将数据库、token、日志、任务输出写入 `.local-data/runtime/`

Linux 如果提示没有执行权限：

```bash
chmod +x run.sh
```

常用启动参数：

| 参数 | 说明 |
|---|---|
| `--admin-password VALUE` | 启动前写入管理员密码到 `.local-data/dashboard.env` |
| `--no-browser` | 启动后不自动打开浏览器 |
| `--skip-install` | 跳过依赖安装检查 |

## 配置

首次启动会在 `.local-data/` 中生成本地配置文件。

长期运行或部署到非本机环境前，请至少检查：

| 配置项 | 说明 |
|---|---|
| 监听地址 | 默认 `127.0.0.1` |
| 监听端口 | 默认 `8787` |
| 访问认证 | 本地一键启动默认关闭；多人或远程访问必须开启 |
| 管理页密码 | 保护 `/admin` 设置页和管理接口，可留空仅使用 admin token |
| 模型配置 | 用于配置模型 provider 和密钥 |

NiuOne 需要接入大模型后才能驱动完整工作流。X 关注列表监控和美股机构评级日报推荐使用 Grok，并由“开启牛牛美股”开关控制；A 股候选股消息面预检可独立配置具备实时搜索能力的模型；选股后的买卖决策可配置兼容模型，推荐使用 DeepSeek。启动后，管理员可通过 `/admin` 管理运行配置、模型配置和邀请码。

### 选股策略来源

设置页的“选股策略”支持两种来源，二选一激活：

| 来源 | 说明 |
|---|---|
| 内置策略 | 在基础策略、Z 哥、李大霄中选择一个参与 A 股扫描和买卖决策。 |
| 预设文字策略 | 用户输入一段自然语言策略，由买卖决策模型先分析优化为选股、买入、卖出、仓位和时间纪律，再用于本轮决策。 |

常用配置项：

```env
DASHBOARD_STRATEGY_SOURCE=builtin
DASHBOARD_ENABLED_PERSONA_STRATEGIES=zettaranc
DASHBOARD_PRESET_STRATEGY_TEXT=
```

| 配置项 | 说明 |
|---|---|
| `DASHBOARD_STRATEGY_SOURCE` | 策略来源，可取 `builtin` 或 `preset_text`；旧值 `persona` 会兼容为 `builtin`。 |
| `DASHBOARD_ENABLED_PERSONA_STRATEGIES` | 内置策略组选择，可取 `base`、`zettaranc` 或 `li_daxiao_bottom`。变量名为历史兼容保留，现在表示“内置策略组”。 |
| `DASHBOARD_PRESET_STRATEGY_TEXT` | 预设文字策略原文，最多 8000 字；保存时会热应用到后续扫描和买卖决策。 |

当选择 `builtin` 时，系统按当前内置策略组参与 A 股扫描和买卖决策。当选择 `preset_text` 时，内置策略偏好不生效，系统使用基础策略生成中性候选池，并把预设文字交给买卖决策模型优化成可执行规则；如果预设文字为空，本轮不新开仓，只按既有持仓风控卖出或持有。

### 管理员密码

管理员密码用于保护 `/admin` 设置页及其管理接口，包括运行配置、模型配置、邀请码和访问用户管理。它不是普通访问邀请码，而是管理员进入设置页时的额外保护层。

首次启动会生成 `.local-data/dashboard.env`，其中包含：

```env
DASHBOARD_AUTH_ENABLED=0
DASHBOARD_ADMIN_PASSWORD=
```

本地一键启动默认关闭访问认证，且管理员密码为空；此时本机访问 `/admin` 不需要额外密码。长期运行、多人使用或暴露到非本机网络前，建议至少改为：

```env
DASHBOARD_AUTH_ENABLED=1
DASHBOARD_ADMIN_PASSWORD=change-this-to-a-strong-password
```

也可以在一键启动时传入管理员密码，启动脚本会把它保存到 `.local-data/dashboard.env`：

```bash
./run.sh --admin-password "change-this-to-a-strong-password"
```

Windows PowerShell：

```powershell
.\run.ps1 --admin-password "change-this-to-a-strong-password"
```

修改 `.local-data/dashboard.env` 后需要重启服务。也可以在首次启动前通过 `DASHBOARD_ADMIN_PASSWORD` 环境变量提供默认值；配置文件已存在时，建议使用启动参数、设置页或直接编辑配置文件更新。

管理员 token 会在服务启动时自动生成并保存到 `.local-data/runtime/dashboard_admin_token.txt`。开启访问认证后，可以用该 token 进入管理员身份，例如：

```text
http://127.0.0.1:8787/admin?token=<token-from-file>
```

如果 `DASHBOARD_ADMIN_PASSWORD` 为空，admin token 即可访问设置页；如果设置了管理员密码，先通过 admin token 获得管理员身份，再输入管理员密码解锁设置页。请不要把 `.local-data/dashboard.env` 或 `.local-data/runtime/dashboard_admin_token.txt` 提交到 Git。

命令行参数可能留在 shell 历史或短暂出现在进程列表中；对更敏感的部署，建议直接编辑 `.local-data/dashboard.env`，或先启动后在 `/admin` 设置页中修改。

## 运行数据与安全

NiuOne 默认把真实运行数据留在工程目录内的 `.local-data/`，便于本地迁移和备份，也避免源码目录与 secrets 混在一起提交。

| 路径 | 内容 |
|---|---|
| `.local-data/dashboard.env` | 本地运行配置，可能包含模型密钥和管理员密码 |
| `.local-data/.venv/` | 一键启动创建的 Python 虚拟环境 |
| `.local-data/runtime/config.yaml` | 模型 provider 配置 |
| `.local-data/runtime/*.db` | 消息、用户、模拟交易等本地数据库 |
| `.local-data/runtime/cron/` | 定时任务状态和输出 |
| `.local-data/runtime/logs/` | dashboard、定时任务和监控日志 |

`.local-data/` 已被 Git 忽略；公开 issue、日志或截图前，请先确认没有带出 token、API key、管理员密码、数据库路径中的隐私信息。

## 项目结构

```text
.
├── app/                    # 本地服务和任务源码
├── tests/                  # 单元测试
├── scripts/                # 验证、迁移和独立任务脚本
├── docs/                   # 操作文档
├── config/                 # 运行策略说明
├── tools/                  # 本地维护工具
├── dashboard.env.example   # 生产式本地配置示例
├── run.sh                  # macOS/Linux 一键启动
├── run.ps1                 # Windows PowerShell 启动
├── run-dashboard.sh        # dashboard LaunchAgent/后台服务入口
├── run-niuone-cron-scheduler.sh
├── run-x-watchlist-daemon.sh
└── requirements.txt        # Python 依赖清单
```

## 验证

修改代码或配置后，可运行项目自带验证脚本：

```bash
./scripts/validate.sh
```

验证脚本会检查 Python 语法、dashboard 内嵌 JavaScript、Shell/PowerShell 启动脚本，并运行 `tests/` 单元测试。更完整的部署、重启、日志检查和回滚流程见 [docs/OPERATIONS.md](docs/OPERATIONS.md)。

## 内置战法与策略来源

NiuOne 的选股策略由“策略来源”和“内置战法”两层组成。默认使用内置策略来源；也可以在设置页切换到预设文字策略，让买卖决策模型按用户输入的自然语言策略生成本轮执行规则。

内置策略下，基础策略、Z 哥和李大霄是同级概念，一次只启用一个；卖出风控归属于 Z 哥体系，不作为独立策略组。预设文字策略下，基础策略只作为中性候选池，最终规则由买卖决策模型根据用户预设文字生成。

### 内置策略组

内置策略用于给扫描器和买卖决策模型提供固定的选股偏好、仓位纪律和退出约束。当前内置三个同级策略组：

| 策略组 | 包含战法/代理信号 | 定位 |
|---|---|---|
| 基础策略 | 突破确认、趋势回踩 | 通用技术候选池 |
| Z 哥 | 少妇B1、B2确认、B3中继、超级B1、Z哥卖出风控 | Z 哥战法体系代理 |
| 李大霄 | 低估蓝筹、底部发育、逆向情绪和去杠杆防守 | 价值与底部防守代理 |

### 基础策略

基础策略和 Z 哥、李大霄处于同一选择层级，用于给扫描器提供通用技术候选：

- **突破确认**：平台或前高突破后回踩站稳，再作为确认仓处理。
- **趋势回踩**：强趋势股回踩BBI/EMA不破，按低吸仓处理。

### Z 哥

NiuOne 的 A 股策略筛选和模拟交易规则中，参考并实现了 [zettaranc-skill](https://github.com/lululu811/zettaranc-skill) 中整理的 Z 哥选股战法思想。当前归属于 Z 哥的买入战法包括：

- **少妇B1**：J值低位、N型上移、缩量回调、牛绳/BBI约束，强调试错仓和近止损。
- **B2确认**：B1后放量中/大阳确认趋势，拒绝偏滞后或离BBI过远的追高。
- **B3中继**：B2后小阳/十字星分歧转一致，快进快出，T+1开盘不涨走。
- **超级B1**：放量破位洗盘后缩量企稳，J值仍负，只赌一次，未兑现则离场。

归属于 Z 哥体系的卖出风控包括：买入K线/前低止损、硬止损、防卖飞评分、卤煮半仓、S1/S2/S3逃顶、出货五式、白线/BBI破位、峰值回撤/ATR吊灯保护，以及 B3、B2、超级B1 的时间离场纪律。

### 李大霄

李大霄策略参考 [li-daxiao-skill](https://github.com/sherjy/li-daxiao-skill) 的“政策、价值、底部发育、逆向情绪、杠杆风控”框架，用主板高流动性蓝筹、低位企稳、低换手、缩量低波动、反追高和反“黑五类”作为可执行代理信号。

策略元数据集中在 `app/strategy_registry.py`。新增内置策略时，优先在注册表里增加策略组及其 `label/color/desc/scorer/profile/position_limit_pct/aliases`，再在 `app/multi_strategy_screen.py` 中实现对应 `score_xxx(rows)` 评分函数。扫描器会自动遍历当前策略组里的 scorer，并把 `strategy_meta` 输出给 dashboard 和模拟交易模块。

本项目仅在本地模拟交易和研究辅助场景中使用这些公开整理的战法规则，不代表原作者背书，也不构成任何投资建议。若继续扩展或二次分发相关策略说明，请同时保留对 zettaranc-skill 与 li-daxiao-skill 的引用。

## 文档

- [docs/STANDALONE.md](docs/STANDALONE.md)：独立运行说明
- [docs/OPERATIONS.md](docs/OPERATIONS.md)：部署、验证和回滚手册
- [config/runtime-policy.md](config/runtime-policy.md)：运行数据和 secrets 处理策略

## License

NiuOne 使用 [Apache License 2.0](LICENSE) 发布。
