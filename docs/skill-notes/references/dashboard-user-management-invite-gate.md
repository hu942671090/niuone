# Dashboard user-management / invite-gate pattern

Session learning: the Niuniu dashboard was made public-viewable while preserving control through an application-layer user system in `hermes_messages_dashboard.py`.

## Recommended architecture

Use an invite-code activation flow, not a shared password:

1. Unauthenticated viewer hits `/` → redirect to `/login`.
2. Viewer enters invite code + optional nickname.
3. Server validates invite quota/expiry/disabled state.
4. Server creates a per-viewer token (`nv_...`), stores only its SHA-256 hash, and sets an HttpOnly SameSite=Lax cookie (`dashboard_token`).
5. All read APIs require a valid viewer token.
6. Mutating/sensitive APIs require admin role.

This preserves UX while allowing per-user revocation and abuse tracing.

## Durable files

- Auth DB: `~/.hermes/dashboard_users.db`
- Admin token file: `~/.hermes/dashboard_admin_token.txt`
- Tests: `~/.hermes/scripts/test_dashboard_auth.py`

## Tables

`invite_codes`:
- `code` primary key
- `max_uses`, `used_count`
- `expires_at`
- `note`
- `disabled`
- `created_at`

`viewers`:
- `token_hash` primary key; store no raw viewer token
- `token_prefix` for admin display only
- `invite_code`
- `nickname`
- `role` (`viewer` or `admin`)
- `created_at`, `last_seen_at`
- `last_ip`, `user_agent`
- `disabled`

## Route contract

Public / auth routes:
- `GET /login` — login form
- `POST /login` — redeem invite and set cookie
- `GET /logout` — clear cookie

Protected viewer routes:
- `GET /` — dashboard HTML
- all normal `/api/*` reads: `/api/messages`, `/api/indices`, `/api/b1_screen`, `/api/niuniu_practice`, etc.

Admin routes:
- `GET /admin?token=<admin-token>` — management UI
- `GET /api/admin/invites`
- `GET /api/admin/viewers`
- `POST /admin/invite/create` and `/api/admin/invite/create`
- `POST /admin/invite/toggle`
- `POST /admin/viewer/toggle`

## Sensitive endpoints to protect as admin-only

Do not leave these available to normal viewers:
- `/api/b1_screen?force=1`
- `/api/b1_screen/trigger`
- `/api/niuniu_practice/resume`
- `/api/self_optimize/apply`

## Online/user limits

Use environment variables for coarse capacity control:

```bash
DASHBOARD_MAX_ONLINE=100
DASHBOARD_ONLINE_WINDOW_SECONDS=300
```

`DASHBOARD_MAX_ONLINE=0` means unlimited.

## TDD/verification checklist

Before shipping:

```bash
python3 -m py_compile ~/.hermes/scripts/hermes_messages_dashboard.py
python3 ~/.hermes/scripts/test_dashboard_auth.py
python3 - <<'PY'
from pathlib import Path
s=Path('~/.hermes/scripts/hermes_messages_dashboard.py').expanduser().read_text()
html=s.split('INDEX_HTML = r"""',1)[1].split('"""',1)[0]
Path('/tmp/dashboard.js').write_text(html.split('<script>',1)[1].split('</script>',1)[0])
PY
node --check /tmp/dashboard.js
```

Smoke checks:
- unauthenticated `/` returns 303 to `/login`
- unauthenticated `/api/messages?limit=1` returns 401
- `/login` renders 200
- `/admin?token=<admin>` renders 200
- admin can create invite
- invite redemption sets cookie and redirects 303
- cookie can access `/api/messages?limit=1` with 200
- browser can log in with invite and load dashboard without console errors

## Pitfalls

- Protect APIs, not just the HTML shell; otherwise users can bypass `/login` and scrape JSON endpoints directly.
- Store token hashes, not raw viewer tokens. Only show `token_prefix` in the admin UI.
- Keep admin token out of the DB as a source of truth by persisting it in a local file; on startup, ensure the file token exists in the DB as role `admin`.
- Viewer authentication may update `last_seen_at`; use a short online window (e.g. 300s) for approximate online counts.
- Dashboard HTML is cacheable in older versions; once auth is added, prefer `Cache-Control: no-store` or very careful private caching for authenticated pages.
