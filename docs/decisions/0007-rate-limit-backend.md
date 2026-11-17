# 0007 — Rate limiting: in-process by default, Redis when configured

- Status: accepted
- Date: 2026-11-16
- Supersedes: nothing

## Context

The face endpoints are the expensive, abusable surface (`/api/verify`, `/api/verify_liveness`,
`/api/detect_webcam`, `/api/pi/*`). An in-process sliding window is dependency-free and correct for
a single worker, but a multi-worker deployment multiplies the effective budget by the worker count.
Earlier docs and `docker-compose.yml` referred to `RATE_LIMIT_BACKEND=redis` before any Redis code
existed — a documentation overclaim.

## Decision

`backend/app/rate_limit.py` supports two backends:

| `RATE_LIMIT_BACKEND` | Implementation | Semantics |
|---|---|---|
| `memory` (default) | `SlidingWindowLimiter` | per-process sliding window, exact within one worker |
| `redis` | `RedisLimiter` | shared fixed-window counter (`INCR` + `EXPIRE`), one budget across workers |

- The Redis client is imported lazily and `redis` is the only optional dependency; the memory
  backend does not need it.
- If Redis is configured but unreachable, the limiter falls back to the process-local window and
  logs a throttled warning. That is a deliberate availability-over-strictness trade for an abuse
  control, not a security boundary. Authentication and authorization remain fail-closed.
- A `429` carries `Retry-After`.
- The limiter is per client IP. `X-Forwarded-For` is only trusted when `TRUST_PROXY_HEADERS=true`,
  because the header is client-controlled otherwise.

## Consequences

- Single-node installs keep working with zero infrastructure.
- Multi-worker installs get a genuinely shared budget by setting the backend and `REDIS_URL`.
- The fixed window can allow a burst at a minute boundary (up to 2× the limit). Acceptable for
  face matching; would not be acceptable for billing or login throttling without a sliding script.
- Tests inject a fake Redis client, so the suite still runs offline (`tests/test_rate_limit.py`).
