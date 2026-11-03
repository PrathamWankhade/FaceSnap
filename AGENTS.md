# AGENTS.md

Project memory for AI coding agents (and humans). Read this before changing anything.
`CLAUDE.md` is a pointer to this file so Claude Code picks it up too.

---

## 1. What FaceSnap is

A **single-institution campus attendance system**: students enroll a face once, then live
verification, doorway batch, group-photo upload, and camera-stream modes match frames against
enrolled embeddings. Only verified matches become attendance rows.

- Frontend: Next.js 15 / React 19 / TypeScript / Tailwind v4 (`frontend/`)
- Backend: FastAPI + SQLAlchemy + InsightFace ArcFace + Qdrant (`backend/`)
- Identity: Firebase Auth (Google SSO) — **identity only**. The relational DB is the system of record.

**It is not a multi-tenant paid SaaS.** There is no billing, no organization scoping, no per-tenant
isolation. Single institution, three roles. Do not invent tenancy, plans, quotas or subscription
gates. See `docs/decisions/0002-multi-tenancy.md`.

## 2. Hard rules

1. **The browser never declares a match and never writes trusted attendance.** Every attendance row
   is written by FastAPI after a server-side match. No `localStorage` writes, no Firestore writes.
2. **The relational database is the only system of record.** Firestore/Storage are removed. Do not
   reintroduce them, and do not treat Qdrant or the image store as authoritative — both are
   derived and rebuildable.
3. **Roles come from `users.role` in SQL, never from token claims.** Firebase tokens prove
   *who*; the database says *what they may do*.
4. **Fail closed in production.** `APP_ENV=production` refuses to boot with `REQUIRE_AUTH=false`
   or a `*` CORS origin. Dev bypass is development-only. Never weaken `_validate_runtime()`.
5. **Honest claims only.** Never write "CCTV", "certified anti-spoofing", "secure by default",
   "bank-grade", "production-ready", "multi-tenant", or "Postgres in production (done)" unless it
   is actually true and tested. The product limitation list lives in `README.md` § Limitations.
6. **Never commit biometrics or secrets.** No face photos, no `data/`, no `*.db`, no `backend/.env`,
   no `frontend/.env.local`, no service-account JSON, no `NEXT_PUBLIC_` provider keys.
   The Groq key is server-only: `GROQ_API_KEY`, never `NEXT_PUBLIC_GROQ_API_KEY`.
7. **Do not print or echo secrets** in logs, test output, docs, screenshots or shell commands.
8. **Keep the app runnable.** After any change, backend must answer `/api/health` and the frontend
   must pass lint + type-check + build.

## 3. Commands

```bash
# Backend (Python 3.11, venv at backend/.venv)
cd backend
.venv\Scripts\activate                # Windows: source .venv/bin/activate elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000     # dev server
python -m pytest -q                    # offline tests, model stubbed
python -m ruff check app tests         # lint
python -m alembic upgrade head         # apply migrations

# Frontend (Node 20+)
cd frontend
npm ci
npm run dev -- -p 3001                 # dev server
npm run lint                           # ESLint
npx tsc --noEmit                       # type check
npm run build                          # production build
npx playwright test                    # E2E (after `npx playwright install`)
```

CI (`.github/workflows/ci.yml`) runs lint, type-check, build, pytest, ruff and dependency audits
on every push and pull request. **A red check blocks the change** — fix, do not skip.

## 4. Layout

```
frontend/
  app/            # route segments: /, register, student, classroom, cctv, attendance,
                  #   about, contact, api/chat (server-side Groq proxy)
  components/     # AuthProvider, Navigation, ThemeProvider, Chatbot, ErrorBoundary
  lib/            # api.ts (backend client), attendance.ts, firebase.ts, overlay.ts, types.ts
backend/
  app/config.py   # env config + production fail-fast settings
  app/auth.py     # token verification, DB-backed roles, require_roles, require_camera_caller
  app/main.py     # FastAPI app, startup guard, CORS, health
  app/db.py       # SQLAlchemy schema = system of record
  app/rate_limit.py
  app/routes/     # registry, verification, detection, pi_routes
  app/services/   # face_service, liveness_service, vector_service, image_store, camera
  alembic/        # migrations
  tests/          # pytest
docs/             # see §5
```

## 5. Where truth lives

| Question | Read |
|----------|------|
| Personas, scope, non-functional requirements | `docs/system-design.md` |
| Why a choice was made | `docs/decisions/` (ADRs) |
| Architecture, request flow, data model | `docs/ARCHITECTURE.md` |
| Who may call what (route matrix) | `docs/permissions.md` |
| Status codes, errors, pagination, naming | `docs/api-conventions.md` |
| Threat model, secrets, biometrics | `docs/SECURITY.md` |
| What tests exist and how to add them | `docs/testing.md` |
| Where it runs, how it is hosted | `docs/hosting.md` |
| Metrics, logs, alerts, health | `docs/monitoring.md` |
| Cache/derived-store policy | `docs/caching.md` |
| Run the migration / roll back / restore / respond | `docs/runbooks/` |

If code and docs disagree, **the code is what shipped — fix the doc in the same change.**

## 6. Working agreement

- **Small, verifiable changes.** One concern per commit; message = what changed + why.
- **Write the test with the change.** A permission change needs a 401/403 test; a schema change
  needs a migration; a route change needs a `docs/permissions.md` row.
- **Verify before claiming.** Never say "verified" for something you did not run.
- **Preserve prior work.** Do not delete existing docs, tests, or checkpoint content unless the
  change supersedes it and you say so.
- **Decisions go in an ADR.** Anything irreversible (new store, new auth model, new provider,
  tenancy, billing) gets `docs/decisions/NNNN-title.md` first.
- **Reuse existing patterns** (`require_roles`, `apiFetch`, `_audit`, response shapes) before
  adding new ones.

## 7. Current known gaps (do not claim otherwise)

- No staging/production deployment yet; local SQLite + local Qdrant only.
- Liveness is best-effort (rPPG + blink + motion), **not** certified PAD; no spoof-corpus eval.
- No benchmark accuracy number is claimed (no LFW eval run).
- Rate limiter is in-process and single-node unless `RATE_LIMIT_BACKEND=redis`.
- `/cctv` is a single camera stream, not an RTSP/CCTV fleet.
- No retention-expiry job for attendance/biometrics.
