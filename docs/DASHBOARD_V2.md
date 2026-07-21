# Dashboard 增量展示与部署

简体中文 | [English](DASHBOARD_V2_EN.md)

Dashboard 保持原有 `frontend/` 页面布局、栏目和交互不变。公开页面与受管理员密码保护的 `/admin` 共用一个服务和端口；性能优化集中在服务端快照、条件请求、按需加载和 CDN 缓存，不把交易或行情计算下沉到浏览器。

## 架构

```text
行情 / 模型 / 定时任务 / 模拟交易
              │
              ▼
 Dashboard 单进程（默认 0.0.0.0:8787）
   ├── 原公开页面与兼容 API
   ├── /admin 与管理员 API
   └── 后台展示投影（默认每 15 秒）
              │
              ▼
 $DASHBOARD_HOME/public-data/
   ├── latest.json
   ├── manifests/<revision>.json
   └── objects/<sha256>.json
```

浏览器每 15 秒先检查 `/api/v2/public/latest`。该指针通常不足 300 字节，并支持 `ETag` 与 `304 Not Modified`；版本变化时再读取 manifest，只对摘要发生变化的数据区块调用相应接口。完整历史在一个页面会话中成功加载一次，失败时最多每 5 分钟重试一次。

服务端投影由 `app/dashboard/public_projection.py` 的字段白名单构建，通过 `app/dashboard/public_snapshots.py` 原子发布。浏览器请求不会触发交易执行、模型调用或完整历史重算。

## 管理页安全

`/admin` 可以和公开页面使用同一个公网域名。页面本身可打开，但配置读取、保存、模型测试和通知测试等 API 仍要求有效的管理员 Cookie；修改类请求还要求 `X-NiuOne-Action`，并受请求体上限和登录/管理接口限流保护。应设置强管理员密码，并保持 Cloudflare、反向代理和源站使用 HTTPS。

## 运行

```bash
./run.sh
```

打开：

- 公开页面：<http://127.0.0.1:8787/>
- 管理页面：<http://127.0.0.1:8787/admin>

主要配置：

| 配置 | 默认值 | 生效时机 |
|---|---:|---|
| `DASHBOARD_PUBLIC_PROJECTION_ENABLED` | `1` | 重启 |
| `DASHBOARD_PUBLIC_REFRESH_SECONDS` | `15` | 重启 |
| `DASHBOARD_PUBLIC_DATA_DIR` | `$DASHBOARD_HOME/public-data` | 重启 |

## 公网与缓存

Cloudflare Tunnel、Nginx 或 Caddy 只需代理 `8787`。建议：

- `/static/*`：按现有响应头长期缓存；
- `/api/v2/public/objects/*`、`/api/v2/public/manifests/*`：一年 immutable；
- `/api/v2/public/latest`：边缘缓存 5 秒并允许 30 秒 stale-while-revalidate；
- `/admin*`、`/api/admin/*` 和写操作：绝不缓存；
- 其他兼容 API：遵循服务端 `Cache-Control`，不要用一条全站规则强制公开缓存。

如果家庭上行或 Tunnel 路径仍是瓶颈，可把服务部署到靠近访问者的云主机，再由 CDN 缓存静态资源和增量快照。迁移或回滚只改变运行位置和域名回源，不重建账户、交易或消息历史。
