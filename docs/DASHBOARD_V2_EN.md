# Dashboard Incremental Delivery and Deployment

[简体中文](DASHBOARD_V2.md) | English

The Dashboard keeps the existing `frontend/` layout, sections, and interactions. The public page and password-protected `/admin` share one service and port. Performance work is limited to server-side snapshots, conditional requests, lazy loading, and CDN caching; trading and market-data computation never move into the browser.

## Architecture

```text
Market data / models / schedules / simulated trading
                         │
                         ▼
      Single Dashboard process (0.0.0.0:8787 by default)
        ├── existing public page and compatibility APIs
        ├── /admin and administrator APIs
        └── background presentation projection (every 15s)
                         │
                         ▼
           $DASHBOARD_HOME/public-data/
             ├── latest.json
             ├── manifests/<revision>.json
             └── objects/<sha256>.json
```

Every 15 seconds the browser first checks `/api/v2/public/latest`. This pointer is normally smaller than 300 bytes and supports `ETag` and `304 Not Modified`. When the revision changes, the browser reads the manifest and calls the relevant compatibility API only for sections whose digest changed. Complete history loads once after a successful page-session request; failures retry no more than once every five minutes.

`app/dashboard/public_projection.py` builds the allow-listed projection, and `app/dashboard/public_snapshots.py` publishes it atomically. Browser traffic does not execute trades, call models, or rebuild complete history.

## Administrator Security

`/admin` may share the public domain. The page itself can open, but configuration reads, saves, model tests, and notification tests still require a valid administrator cookie. Mutating requests also require `X-NiuOne-Action` and remain protected by body-size and login/administrator rate limits. Use a strong administrator password and HTTPS from Cloudflare or the reverse proxy through to the origin.

## Run

```bash
./run.sh
```

Open:

- Public page: <http://127.0.0.1:8787/>
- Administrator page: <http://127.0.0.1:8787/admin>

| Setting | Default | Effective |
|---|---:|---|
| `DASHBOARD_PUBLIC_PROJECTION_ENABLED` | `1` | restart |
| `DASHBOARD_PUBLIC_REFRESH_SECONDS` | `15` | restart |
| `DASHBOARD_PUBLIC_DATA_DIR` | `$DASHBOARD_HOME/public-data` | restart |

## Public Caching

Cloudflare Tunnel, Nginx, or Caddy needs to proxy only port `8787`. Recommended policies:

- `/static/*`: cache long-term according to the existing response headers;
- `/api/v2/public/objects/*` and `/api/v2/public/manifests/*`: one year, immutable;
- `/api/v2/public/latest`: five-second edge caching with 30-second stale-while-revalidate;
- `/admin*`, `/api/admin/*`, and mutating requests: never cache;
- other compatibility APIs: honor the server's `Cache-Control`; do not force one public cache rule across the site.

If the home uplink or Tunnel path remains the bottleneck, run the same single-port service on a cloud host near users and let the CDN cache static assets and incremental snapshots. Migration and rollback change only the runtime location and domain origin; account, trade, and message history are not rebuilt.
