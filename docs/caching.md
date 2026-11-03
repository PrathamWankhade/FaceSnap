# Caching & derived stores

FaceSnap has exactly one system of record (see [`decisions/0004`](decisions/0004-sql-system-of-record.md)).
Everything else in this document is a **cache or derived index**: useful, disposable, and never
the thing we apologise for losing.

## Inventory

| Store | Kind | Authority | Rebuild command | Lost ⇒ |
|-------|------|-----------|-----------------|--------|
| SQL (SQLite/Postgres) | **system of record** | authoritative | *no rebuild — back it up* | unrecoverable without a restore |
| Qdrant `students` collection | derived vector index | never authoritative | `POST /api/admin/backfill-embeddings` | recognition stops; attendance history intact |
| `FACE_IMAGE_DIR/*.jpg` | original biometrics | authoritative for the *original photo* | no rebuild — back it up | re-enrollment required; embeddings unverifiable |
| InsightFace model files | local model cache | n/a (re-downloadable) | re-run the app (auto-download) | cold start only |
| In-process rate-limit window | derived counter | n/a | automatic | limits reset; fail-open by design |
| HTTP/browser caches (UI) | client cache | n/a | reload | stale UI until reload |

## Rules

1. **Reads go to SQL.** No endpoint may answer from Qdrant or the image store alone.
2. **Writes go to SQL first**, then the derived index. If the index write fails the row is still
   correct and the UI reports `embedding_indexed: false` rather than failing the request.
3. **Derived indexes must be idempotent and deterministic.** Qdrant point IDs derive from the user
   id, so re-enrollment *updates* a point instead of duplicating it.
4. **A derived store must never widen permissions.** Nothing is served from a cache that the caller
   could not read from SQL.
5. **No new cache without an ADR** — and the ADR must state the invalidation rule and the
   behaviour when the cache is empty or stale (not just the speedup).

## Invalidation model

- Enrollment / profile update / delete → immediate Qdrant upsert/delete in the same request
  (best-effort) + image store write/delete.
- Student deletion → SQL cascade, then image delete, then vector delete, then an audit row.
  If a later step fails, `backfill-embeddings` reconciles the index from SQL.
- Attendance → **no cache**. Always written and read from SQL.
- Reconciliation tool: `POST /api/admin/backfill-embeddings` (admin, audited). Treat it as the
  supported repair path for index drift — document any incident where it was needed.

## What we deliberately do not cache

- Attendance and analytics — computed per request from SQL; single-institution volumes make this
  cheap, and a stale attendance count is worse than a slow one.
- Authorization decisions — roles are read per request so a demotion takes effect immediately.
- Face matches — never memoised across requests; every verification recomputes.

## Known gaps (honest)

- The rate-limit window is **per process**; with N workers the effective limit is N× higher. Fix:
  a shared store (Redis) or edge-level limiting — see [`hosting.md`](hosting.md).
- Qdrant runs in local (file-backed) mode: one node, no replication.
- No response caching (ETag/`Cache-Control`) on GET endpoints yet; defaults are used.
