# NiuOne · 牛牛1号

<p align="left">
  <a href="https://github.com/kunkundi/niuone/actions/workflows/ci.yml"><img src="https://github.com/kunkundi/niuone/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License" /></a>
  <a href="https://linux.do"><img src="https://shorturl.at/ggSqS" alt="LINUX DO" /></a>
</p>

NiuOne 是一个本地优先的市场信息聚合与研究工作台。项目将行情看板、信息摘要、关注源监控、定时任务、历史归档与模拟复盘整合到统一界面，适合个人研究、数据观察和自动化工作流实验。

在线演示：<https://niuone.cn>

> 本项目用于技术研究与信息整理，不提供个性化投资建议，不连接券商账户，也不执行真实资金交易。

## 功能概览

- **统一看板**：集中展示指数、板块、市场热度、资金流和历史消息。
- **信息聚合**：整理 A 股盘面、美股市场摘要、机构评级和自定义关注源。
- **智能摘要**：可接入兼容的大模型服务，对多来源信息进行归纳和结构化整理。
- **模拟复盘**：通过本地模拟账户记录研究过程、状态变化与历史结果。
- **自动化任务**：支持定时采集、生成摘要、归档和后台监控。
- **本地优先**：配置、数据库、日志和任务输出默认保存在本机，不随源码提交。

具体研究方法与实验性策略不在主 README 展开，参见 [策略研究说明](docs/strategies/README.md)。

## 系统要求

| 依赖 | 要求 | 用途 |
|---|---|---|
| Python | 3.11+ | 运行服务、任务脚本和本地工具 |
| Git | 推荐最新稳定版 | 获取和更新项目 |
| 浏览器 | Chrome、Edge、Safari、Firefox 等现代浏览器 | 访问本地工作台 |
| 网络 | 首次运行需访问 PyPI | 安装 Python 依赖 |

参与开发或运行完整验证时，还需要 Node.js 18+，用于检查 dashboard 中的 JavaScript。

## 快速部署

克隆项目：

```bash
git clone https://github.com/kunkundi/niuone.git
cd niuone
```

macOS / Linux：

```bash
./run.sh
```

Linux 如果提示没有执行权限：

```bash
chmod +x run.sh
./run.sh
```

Windows 可双击 `run.bat`，或在 CMD 中执行：

```cmd
run.bat
```

启动完成后访问：

```text
http://127.0.0.1:8787/
```

首次运行会自动：

1. 创建 `.local-data/` 私有运行目录；
2. 创建 `.local-data/.venv/` Python 虚拟环境；
3. 安装 `requirements.txt` 中的依赖；
4. 生成 `.local-data/dashboard.env`；
5. 初始化运行目录并启动本地 dashboard。

### 常用启动参数

| 参数 | 说明 |
|---|---|
| `--port VALUE` | 设置并保存 dashboard 端口 |
| `--no-browser` | 启动后不自动打开浏览器 |
| `--skip-install` | 跳过依赖安装检查 |
| `--service` | 注册并启动当前平台的长期运行服务 |

例如，使用 `8877` 端口且不自动打开浏览器：

```bash
./run.sh --port 8877 --no-browser
```

Windows：

```cmd
run.bat --port 8877 --no-browser
```

如需将运行数据保存在其他位置，可设置：

```bash
NIUONE_LOCAL_DATA_DIR=/path/to/private-data ./run.sh
```

## 容器化部署

项目提供单一镜像和 Compose 编排。Compose 会启动 dashboard、定时调度器和 X 关注源守护进程，并通过同一个 `niuone-data` volume 持久化配置、数据库、日志和任务输出。

从源码构建并启动：

```bash
docker compose up -d --build
docker compose ps
```

默认仅在宿主机 `127.0.0.1:8787` 提供服务，访问 <http://127.0.0.1:8787/>。查看日志或停止服务：

```bash
docker compose logs -f
docker compose down
```

从 Docker Hub 部署指定版本：

```bash
export NIUONE_IMAGE=kunkundi/niuone:v0.0.1
docker compose pull
docker compose up -d --no-build
```

如需修改宿主机端口，可设置 `NIUONE_PORT`。只有在已经配置反向代理、HTTPS 和独立访问控制时，才应将监听地址改为 `0.0.0.0`：

```bash
NIUONE_BIND_ADDRESS=0.0.0.0 NIUONE_PORT=8877 docker compose up -d
```

> 当前管理入口不提供独立登录保护，不要直接暴露到公网。运行配置与密钥保存在 volume 的 `/data/dashboard.env` 和 `/data/runtime/` 中，不会打入镜像。

## 首次配置

基础页面无需模型密钥即可启动。信息检索、智能摘要和部分自动化流程需要额外配置外部服务。

启动后通过页面中的设置入口完成配置；配置会写入本地 `.local-data/`，无需修改源码。建议首次使用时依次完成：

1. 设置需要启用的数据源与自动化任务；
2. 按需配置兼容的模型服务地址、模型名称和 API Key；
3. 如需限制管理入口访问，在设置页启用管理员保护；
4. 重启服务，使所有需要重启的配置生效。

默认服务只监听 `127.0.0.1`。如需通过局域网或公网访问，请先配置反向代理、HTTPS 和独立的访问控制，不要直接暴露本地管理入口。

## 运行数据与安全

本地数据默认位于 `.local-data/`：

```text
.local-data/
├── dashboard.env          # 本地运行配置，可能包含密钥
├── .venv/                 # Python 虚拟环境
├── runtime/
│   ├── config.yaml        # 服务与模型配置
│   ├── *.db               # 本地数据库
│   ├── cron/              # 定时任务状态与输出
│   └── logs/              # 运行日志
└── backups/               # 本地部署备份
```

`.local-data/` 已被 Git 忽略。提交代码、公开日志或分享截图前，请确认其中不包含 API Key、管理员凭据、数据库内容或其他个人数据。

## 长期运行与更新

使用同一个一键启动脚本增加 `--service` 参数，即可完成依赖初始化、原生后台服务注册和启动。

macOS / Linux：

```bash
./run.sh --service
```

Windows：

```cmd
run.bat --service
```

macOS 使用 LaunchAgent，Linux 使用用户级 systemd，Windows 使用任务计划程序。该模式会托管 dashboard、定时调度器和关注源监控三个进程；未启用的关注源功能会保持休眠。

需要指定端口或禁止自动打开浏览器时，可组合参数：

```bash
./run.sh --service --port 8877 --no-browser
```

各平台的状态、重启、卸载和无人值守运行说明参见 [独立运行说明](docs/STANDALONE.md)。部署更新、日志检查、备份和回滚步骤参见 [部署、验证和回滚手册](docs/OPERATIONS.md)。

## 项目结构

```text
.
├── app/                    # dashboard、数据适配器和任务源码
├── config/                 # 运行策略与安全约定
├── docs/                   # 部署、运行和研究文档
├── scripts/                # 验证、部署和独立任务脚本
├── tests/                  # 自动化测试
├── tools/                  # 本地维护工具
├── dashboard.env.example   # 配置示例
├── run.sh                  # macOS / Linux 一键启动
├── run.bat                 # Windows 一键启动
└── requirements.txt        # Python 依赖
```

## 验证

服务启动后可执行健康检查：

```bash
curl -s -o /dev/null -w 'HTTP:%{http_code} TOTAL:%{time_total}\n' http://127.0.0.1:8787/
curl -s -o /dev/null -w 'HTTP:%{http_code} TOTAL:%{time_total}\n' 'http://127.0.0.1:8787/api/messages?limit=1'
```

预期均返回 `HTTP:200`。

开发验证：

```bash
./scripts/validate.sh
```

验证脚本会检查 Python、JavaScript、Shell、Windows BAT 入口，并运行 `tests/` 下的自动化测试。

## 常见问题

### 找不到 `python3`

安装 Python 3.11 或更高版本，并确认 `python3 --version` 可以正常输出版本号。Windows 启动脚本会依次尝试 `python`、`py -3` 和 `python3`。

### 依赖安装失败

首次启动需要从 PyPI 下载依赖。请检查网络和本机 pip 配置，然后重新运行启动脚本。

### 端口 `8787` 已被占用

指定其他端口：

```bash
./run.sh --port 8877
```

### 页面可访问，但部分内容没有生成

检查设置页中的数据源、模型服务、功能开关和任务时间，并确认相关外部服务可访问。更多排查方法见 [部署、验证和回滚手册](docs/OPERATIONS.md)。

## 文档

- [策略研究说明](docs/strategies/README.md)
- [独立运行说明](docs/STANDALONE.md)
- [部署、验证和回滚手册](docs/OPERATIONS.md)
- [运行数据和敏感信息处理策略](config/runtime-policy.md)

## License

NiuOne 使用 [Apache License 2.0](LICENSE) 发布。
