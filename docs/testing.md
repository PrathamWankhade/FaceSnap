# Testing

Four layers. Each layer has a job the next one cannot do — do not treat a green unit suite as
evidence that the product works.

| Layer | Tool | Proves | Runs |
|-------|------|--------|------|
| Unit / integration | `pytest` (backend) | matching math, permissions, idempotency, config guards | CI + locally |
| Static | `ruff`, `tsc`, `eslint` | style, unused code, type errors before execution | CI |
| End-to-end | Playwright | real browser → real routes → real API, user-visible states | CI + locally |
| Load | `scripts/load-test.js` | behaviour under concurrency (rate limits, races) | on demand |

## Backend: `pytest`

```bash
cd backend
python -m pytest -q              # full suite, offline, model stubbed
python -m pytest tests/test_permissions.py -q
python -m pytest -k "idempotent" -q
```

- The face model, vector index and camera are **stubbed**, so the suite needs no model download,
  no network and no GPU. DB, routing, auth resolution and idempotency are real.
- Tests build/tear down their own SQLite schema (`Base.metadata.drop_all` / `create_all`), so they
  never touch `backend/facesnap.db`.
- `tests/conftest.py` pins `DATABASE_URL` to a temp file **before** the app imports config.

| File | Covers |
|------|--------|
| `tests/test_registry_api.py` | enrollment upsert/conflict, attendance idempotency (app + DB index), session-scoped marks, analytics, filters, staff/student scoping |
| `tests/test_permissions.py` | 401 without a token, 403 for the wrong role, **cross-user read attempts** for every self-scoped route |
| `tests/test_security.py` | production fail-fast guards, dev-bypass refusal, staff-only camera routes, service-key gate, proxy-header trust |
| `tests/test_liveness.py` | static/repeated frames rejected, measured-FPS handling, frame-count bounds |
| `tests/test_face_service.py` | guardrails (size/face count), distance maths, threshold behaviour |

### Adding a test

1. New route → add a row to `docs/permissions.md` **and** a case in `test_permissions.py`
   (401 unauthenticated, 403 wrong role, and the cross-user attempt if the route is self-scoped).
2. New schema change → migration + a test that exercises the constraint (not just the column).
3. Bug fix → a test that fails before the fix. No fixes without a regression test.

## Static

```bash
cd backend && python -m ruff check app tests     # lint + common bug patterns
cd frontend && npm run lint && npx tsc --noEmit  # ESLint + types
```

Ruff rules live in `backend/ruff.toml`. Keep the lint set small and correctness-oriented
(`E`, `F`, `W`, `I`, `B`, `UP`) rather than a style crusade; `--fix` handles import order.

## End-to-end: Playwright

```bash
cd frontend
npm run test:e2e            # runs the Next.js dev server itself via webServer config
npx playwright test --headed # watch it
```

Specs live in `frontend/e2e/`. What is covered and **what deliberately is not**:

- Covered: landing renders, auth-gated routes redirect when signed out, role-aware navigation,
  the registration flow's validation states, attendance history rendering, and that the frontend
  fails *visibly* (no silent success) when the backend is down.
- **Not covered: a real webcam liveness scan.** The liveness service correctly rejects synthetic
  video and repeated frames, so a faked camera would test the fake, not the product. Real camera
  verification is a **manual test** — the checklist is below, and that is an honest limitation,
  not a gap we paper over with a mock that always passes.
- CI runs the browser suite in headless Chromium only; other engines are a local concern.

## Load

```bash
node scripts/load-test.js --base http://127.0.0.1:8002 --rps 20 --seconds 30
```

A dependency-free Node script that fires concurrent requests at the rate-limited and
idempotency-sensitive endpoints and reports p50/p95/p99, error counts and `429` counts.
Used to answer two questions: does the limiter actually engage, and does concurrent attendance
produce **one** row rather than two. It is not a capacity benchmark and no SLA is derived from it.

## Manual checklist (camera + SSO)

Run before declaring a release-ready change:

1. Google sign-in works; role is correct in `/api/me`.
2. `/register` enrolls a real face (exactly one face enforced; consent notice visible).
3. `/student`: live scan passes for the enrolled person, **fails** for a different person,
   and **fails** when the camera is covered with a photo.
4. Attendance shows *verified* and *recorded* as separate states; repeat scan says
   "already recorded" and does not create a second row.
5. `/classroom` and `/cctv` refuse to start for a student account (403 surfaced as an error,
   not a broken page).
6. Deleting the profile removes photo + embedding + history and the student can re-enroll.

## CI

`.github/workflows/ci.yml` runs on every push and PR:

- frontend: `lint` → `tsc` → `build`
- backend: `ruff check` → `pytest`
- dependency audit: `pip-audit` (Python) and `npm audit` (JS)
- Playwright job on `main`

A red check blocks the change. CI is a floor, not a ceiling — it never proves the camera path.
