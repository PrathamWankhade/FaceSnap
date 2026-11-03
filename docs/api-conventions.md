# API conventions

Base URL: the backend origin (`http://127.0.0.1:8002` locally, your HTTPS origin in staging/ prod).
All routes are JSON under `/api/**`. Interactive docs: `/docs` (FastAPI/OpenAPI) — do not hand-write
a second reference; README keeps the human summary and this file keeps the rules.

## Request

- **Auth**: `Authorization: Bearer <Firebase ID token>`. Cameras/devices may substitute
  `X-Service-Key: <PI_SERVICE_KEY>`.
- **Correlation**: clients may send `X-Request-Id`; if absent the server mints one. It is echoed in
  the `X-Request-Id` response header and attached to every log line for that request.
- **Content type**: `application/json` (except image uploads as base64 data URLs inside JSON).
- **Body size**: image fields are capped (`8 MB` per image, `4096 px` per side, max 60 liveness
  frames). Oversized → `413`.
- **Timestamps**: ISO-8601. Naive timestamps are interpreted as **UTC** (`db.as_utc`,
  `db.to_naive_utc` normalise both directions).

## Response

Success shapes are flat objects or `{ "<resource>": [...], "total": n }`:

```jsonc
{ "students": [ ... ], "total": 12 }          // lists
{ "record": { ... }, "duplicate": true }      // writes
```

- **Lists are capped, not cursor-paginated** (`limit` with a documented `ge`/`le` bound).
  Cursor pagination is deferred until any endpoint actually exceeds its cap — recorded as a known
  limitation, not silently ignored.
- **Write endpoints report idempotency explicitly**: `duplicate: true` means "already recorded,
  here is the winner" and is a `200`, not an error.

## Errors

FastAPI's shape, always: `{ "detail": "<human-readable message>" }`
(array-of-objects for validation failures).

| Status | Meaning | Typical trigger |
|--------|---------|-----------------|
| `400` | Malformed input | undecodable base64, bad date |
| `401` | Not authenticated | missing/empty/invalid/expired bearer token, no subject in token |
| `403` | Authenticated but not allowed | wrong role, camera endpoint called by a student, staff-only route |
| `404` | Object missing **or** not visible to you | unknown id; also used when a self-scoped row does not exist |
| `409` | Conflict | roll number already registered; attendance race lost |
| `413` | Payload too large | > 8 MB image, > 60 frames |
| `422` | Semantically invalid | enrollment without exactly one face, no embedding extractable |
| `429` | Rate limited | `RATE_LIMIT_PER_MINUTE` exceeded (with `Retry-After`) |
| `503` | Dependency unavailable | face model not loaded, auth service not configured, model warming |

`5xx` must never be returned for user error. `403` must not reveal whether the target object exists
beyond what the caller already knows.

## Naming

- Paths: `plural nouns`, `snake_case` reserved for **query/body fields**
  (`student_uid`, `frame_interval_ms`, `date_from` → aliased to `from`).
- Response fields: `camelCase` in `registry.py` serializers (`startsAt`, `studentsTotal`,
  `livenessScore`); backend-internal names stay `snake_case`.
- Booleans that gate UI state are explicit: `duplicate`, `created`, `embedding_indexed`, `match`.

## Auth headers client-side

`frontend/lib/attendance.ts` → `authHeaders()` is the only place the frontend attaches a token.
`frontend/lib/api.ts` → `apiFetch()` is the only place it turns a non-2xx into `ApiError`.
Reuse them; do not hand-roll `fetch` against the backend in a component.

## Rate limits

Applied with `Depends(rate_limit_face)` on the expensive face/verify routes. Key = direct client
IP; `X-Forwarded-For` is only honoured when `TRUST_PROXY_HEADERS=true` (a proxy you control must
overwrite it). `RATE_LIMIT_PER_MINUTE=0` disables. Single-node, in-process — see
[`hosting.md`](hosting.md) for the multi-worker story.

## Health

| Endpoint | Purpose | Auth | May touch |
|----------|---------|------|-----------|
| `GET /api/health/live` | process is up (uptime probe) | — | nothing |
| `GET /api/health` | readiness of db / vector / face model / camera | — | cheap DB counts only |
| `GET /` | human/agent summary | — | cheap DB counts |

Health must stay fast (NFR-O1) and must not trigger model inference.
