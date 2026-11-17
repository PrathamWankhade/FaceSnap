# Monitoring, logging & health

Goal: when something breaks at 2 a.m., the first question — *is it up, which component, and which
request caused it* — is answerable without attaching a debugger.

## Health endpoints

| Endpoint | Purpose | Cost | Expected status |
|----------|---------|------|-----------------|
| `GET /api/health/live` | process is running (uptime/ liveness probe) | none — no I/O | `200` always while serving |
| `GET /api/health` | readiness: `database`, `vector_db`, `face_model`, plus the **optional** `camera` state and counts | two cheap `COUNT(*)` queries | `200` `ok:true` when the hard dependencies are ready · `503` when one is down · a disabled camera is reported but does not fail readiness |
| `GET /` | human/agent summary | same as health | `200` |

Rules:
- Health **never** triggers model inference and never loads an image (NFR-O1).
- Probe liveness with `/api/health/live`, readiness with `/api/health`. Do not restart a process
  because a *dependency* failed a readiness check — that is a crash loop.
- `face_model_ready: false` is a real state (model missing/failed to load): the API answers `503`
  on recognition routes instead of pretending.

## Metrics

`GET /api/metrics` renders Prometheus text format from an in-process registry
(`backend/app/metrics.py`, no client library):

```
facesnap_requests_total{method="POST",route="/api/attendance",status="200"} 12
facesnap_request_duration_seconds_bucket{method="POST",route="/api/verify_liveness",le="2.5"} 41
facesnap_request_duration_seconds_sum{...} / _count{...}          # per route
facesnap_rate_limited_total                                       # 429s
facesnap_auth_failures_total{status="401"|"403"}
facesnap_process_uptime_seconds
```

- Counters are **label-light on purpose**: `method`, bounded `route` template, `status`. The route
  label comes from the matched route (`/api/students/{student_id}`), never a raw path — a raw path
  with a student id would be a cardinality bomb and leak identifiers.
- No PII in metric labels, ever.
- Latency buckets are `0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10` seconds. `p95` for the recognition
  routes is computed from this histogram; there is **no published SLO yet** because no
  representative deployment has been benchmarked. Treat the numbers as observed, not promised.
- Exposition is plain text and unauthenticated: aggregate counts only. Restrict it at the proxy if
  your network requires that.
- Registration happens in the request middleware, so a scrape sees requests completed *before* it;
  the scrape itself appears on the next one.

## Logs

- **Structured JSON on stdout in production**, human-readable on stderr in development
  (`LOG_FORMAT=json|text`, `LOG_LEVEL=INFO`).
- Every request line carries: `ts`, `level`, `event`, `request_id`, `method`, `route`, `status`,
  `duration_ms`, `client_ip`. Optional `uid`/`role` when a user was resolved.
- **Request IDs**: inbound `X-Request-Id` is honoured (sanitised), otherwise generated; returned in
  the response header; attached to every log line and to error responses so a user-reported
  screenshot can be matched to a server line.
- Never logged: bearer tokens, `X-Service-Key`, image/base64 payloads, embedding vectors, Groq/Firebase
  keys, full query strings with filters. `Authorization` is redacted at the middleware boundary.
- Exceptions are logged with the traceback at `ERROR` and return a generic `{"detail": "..."}`
  plus the `request_id` — internal messages stay out of client responses.

## Alerting (targets once a host exists)

| Signal | Alert when | Why |
|--------|-----------|-----|
| `/api/health` 5xx / timeout | 3 consecutive failures | hard dependency down |
| `facesnap_requests_total status="5xx"` | > 5% of traffic for 5 min | regression shipped |
| `facesnap_rate_limited_total` spike | sudden step change | misconfigured client **or** abuse |
| `facesnap_auth_failures_total status="401"` | sustained climb | clock skew, expired Firebase config, or credential stuffing |
| uptime probe on `/api/health/live` | down 60 s | process dead |
| disk on `FACE_IMAGE_DIR` + backup volume | < 20% free | silent data-loss risk |
| backup job | no successful run in 24 h | NFR-O4 |

Concrete wiring (provider, channel, thresholds) is a decision for
[`hosting.md`](hosting.md) § observability once a host is chosen — no provider is claimed today.

## Error tracking

Unhandled exceptions are logged with stack traces and `request_id`. External error tracking
(Sentry or equivalent) is **not integrated**: it needs an account, a DSN and a data-flow decision
(what of our payloads is safe to ship to a third party — for a biometric product, mostly none).
Recorded as a known gap rather than pretended.

## Dashboards worth having

1. **Golden signals per route**: rate, error %, p95 latency (from `facesnap_request_duration_seconds_*`).
2. **Recognition pipeline**: `429` rate, `403` rate, `503` from face-model-not-ready.
3. **Business sanity**: `students_in_db` and `attendance_rows` from `/api/health` (a drop to 0
   during a deploy means we booted against the wrong database).

## Runbooks

Incidents: [`runbooks/incident-response.md`](runbooks/incident-response.md).
Deploys and rollback: [`runbooks/deploy.md`](runbooks/deploy.md),
[`runbooks/rollback.md`](runbooks/rollback.md).
Backups: [`runbooks/backup-restore.md`](runbooks/backup-restore.md).

## SLOs (published targets)

| Endpoint | p50 target | p95 target |
|----------|-----------|-----------|
| GET /api/health | < 50 ms | < 100 ms |
| POST /api/detect_webcam | < 500 ms | < 2 s |
| POST /api/verify_liveness | < 2 s | < 3 s |

Targets are aspirational and must be validated with scripts/load-test.js against a running server. CI does not gate on them.
