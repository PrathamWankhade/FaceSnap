# Hosting & deployment

**Status: designed and containerised, not yet deployed.** There is no staging or production host
today and this document deliberately makes no uptime, SLA or compliance claim. It records what is
ready, what a deployment needs, and the decisions still owned by a human.

## What exists today

| Piece | State |
|-------|-------|
| Containers | `backend/Dockerfile` (non-root, healthcheck), `frontend/Dockerfile` (Next standalone) |
| Local stack | `docker-compose.yml` — API + web + Postgres + Qdrant + Redis volumes |
| CI | lint/type-check/build/tests/ruff/dependency audit on every push (`.github/workflows/ci.yml`) |
| Migrations | Alembic, applied at startup or as a deploy step ([`runbooks/migrate.md`](runbooks/migrate.md)) |
| Backups | `scripts/backup.sh` + restore path, tested manually ([`runbooks/backup-restore.md`](runbooks/backup-restore.md)) |
| IaC / host provisioning | **none** |
| Staging / production environment | **none** |

## Topology (target)

```
                    ┌─ CDN / TLS terminator ─┐
   browser ────────►│  next.js (standalone)  │  NEXT_PUBLIC_BACKEND_URL
                    └───────────┬────────────┘
                                │ HTTPS + Firebase ID token
                    ┌───────────▼────────────┐
                    │  uvicorn / FastAPI     │──► Postgres      (system of record, persistent volume)
                    │  (2 workers, no reload)│──► Qdrant        (persistent volume)
                    │                        │──► FACE_IMAGE_DIR (persistent volume)
                    └───────────┬────────────┘
                                │
                     rate limit: Redis (single-node today: in-process)
```

Minimum for a real deployment: TLS everywhere, a Postgres server with point-in-time backup,
persistent volumes for `FACE_IMAGE_DIR`/`QDRANT_PATH`, `APP_ENV=production`, and a Firebase
service account mounted as a secret. The backend needs ~2 GB RAM for the models.

## Required environment (production)

Backend — `APP_ENV=production`, `REQUIRE_AUTH=true`, explicit `CORS_ORIGINS` (no `*`),
`DATABASE_URL=postgresql+psycopg://…`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `ADMIN_EMAILS`,
`TRUST_PROXY_HEADERS=true` **only** behind a proxy that overwrites `X-Forwarded-For`,
`PI_SERVICE_KEY` for devices, `LOG_FORMAT=json`, `AUTO_MIGRATE` per your deploy style.
The app **refuses to start** with auth off or wildcard CORS — that is intentional; fix the config,
do not disable the guard.

Frontend — all `NEXT_PUBLIC_FIREBASE_*`, `NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_APP_URL`,
server-side `GROQ_API_KEY` (never `NEXT_PUBLIC_`).

## Deploy

Follow [`runbooks/deploy.md`](runbooks/deploy.md): back up → migrate → start new code → verify
`/api/health` → smoke test → keep the previous image for
[`runbooks/rollback.md`](runbooks/rollback.md).

## Decisions still owed by a human

These need an account, a budget or a policy — an agent cannot choose them, and choosing silently
would be pretending:

1. **Provider & tier** (Vercel+Railway, Fly, Hetzner+VPS, AWS, college on-prem). Affects price,
   region (biometric data residency!), and whether Qdrant runs local-mode or managed.
2. **Data residency / retention policy** — where biometric photos may live, for how long, and who
   may delete them. Institutional review is required before real student data.
3. **Domain, TLS and DNS** ownership.
4. **Uptime/error-budget** and who gets paged (there is no on-call for this project today).
5. **Error-tracking vendor** and what payload is permitted to leave the network.

## Known gaps

- No infrastructure-as-code; a host would be configured by hand and is therefore not reproducible.
- No blue/green or canary: rollback is redeploy-previous + `alembic downgrade -1`.
- Rate limiting is per-process (see [`caching.md`](caching.md)); the compose file includes Redis so
  a shared limiter can be enabled without a redesign.
- No CDN/edge caching layer, no WAF, no DDoS protection.
- SQLite is a dev convenience only — multi-worker production must use Postgres.
