# Testing

Four layers. Each layer has a job the next one cannot do — do not treat a green unit suite as
evidence that the product works.

| Layer | Tool | Proves | Runs |
|-------|------|--------|------|
| Unit / integration | `pytest` (backend) | matching math, permissions, idempotency, config guards, metrics | CI + locally |
| Static | `ruff`, `tsc`, `eslint` | style, unused code, type errors before execution | CI |
| End-to-end | Playwright | real browser → real routes → user-visible auth states | CI + locally |
| Load | `scripts/load-test.js` | behaviour under concurrency (rate limits, races) | on demand |
| Recognition quality | `scripts/evaluate_recognition.py` | FAR/FRR/EER/accuracy on a named dataset | on demand (needs data) |

## Backend: `pytest`

```bash
cd backend
pip install -r requirements-dev.txt   # runtime deps + ruff + pip-audit
python -m pytest -q                   # full suite, offline, model stubbed
python -m pytest tests/test_permissions.py -q
python -m pytest -k "idempotent" -q
```

`requirements-dev.txt` layers lint/audit tooling on `requirements.txt`, so a fresh checkout and
CI install exactly the same set.

- The face model, vector index and camera are **stubbed**, so the suite needs no model download,
  no network and no GPU. DB, routing, auth resolution and idempotency are real.
- Tests build/tear down their own SQLite schema (`Base.metadata.drop_all` / `create_all`), so they
  never touch `backend/facesnap.db`.
- `tests/conftest.py` pins `DATABASE_URL` to a temp file **before** the app imports config.

| File | Covers |
|------|--------|
| `tests/test_registry_api.py` | enrollment upsert/conflict, attendance idempotency (app + DB index), session-scoped marks, analytics, filters, staff/student scoping |
| `tests/test_permissions.py` | 403 for the wrong role and **cross-user read attempts** for self-scoped routes (auth is overridden per test; production 401 is covered in `test_security.py`) |
| `tests/test_security.py` | production fail-fast guards, dev-bypass refusal, staff-only camera routes, service-key gate, proxy-header trust |
| `tests/test_liveness.py` | static/repeated frames rejected, measured-FPS handling, frame-count bounds |
| `tests/test_face_service.py` | guardrails (size/face count), distance maths, threshold behaviour |
| `tests/test_preprocessing.py` | low-light enhancement is a no-op on bright frames, lifts dark frames, caps gain |
| `tests/test_metrics.py` | counter/histogram rendering, cumulative buckets, label escaping, bounded routes |
| `tests/test_evaluation.py` | confusion counts, threshold sweep, monotonic FAR/FRR, EER interpolation, input validation |
| `tests/test_rate_limit.py` | Redis window counting, outage fallback, `limit=0`, reset |
| `tests/test_enrollment_quality.py` | enrollment gate: single-face requirement, size, blur, detection confidence, pose, embedding validity |
| `tests/test_retention.py` | retention dry-run vs. apply, cut-off bounds, audit row, zero/negative-window guard |
| `tests/test_backup_restore.py` | SQLite online backup is a consistent copy; restore replaces the target; missing source errors |

### Adding a test

1. New route → add a row to `docs/permissions.md` **and** a case in `test_permissions.py`
   (401 unauthenticated, 403 wrong role, and the cross-user attempt if the route is self-scoped).
2. New schema change → migration + a test that exercises the constraint (not just the column).
3. Bug fix → a test that fails before the fix. No fixes without a regression test.

## Static

```bash
cd backend && python -m ruff check app tests     # correctness lint (E4/E7/E9/F)
cd frontend && npm run lint && npx tsc --noEmit  # ESLint + types
```

Ruff rules live in `backend/ruff.toml`: error-only pyflakes/pycodestyle (`E4`, `E7`, `E9`, `F`).
Line length and the bugbear/bandit families are deliberately not enforced — `Depends(...)` in
default arguments is the FastAPI idiom used throughout `routes/`, and service code catches broad
exceptions on purpose. `--fix` handles unused imports.

## Recognition quality

```bash
cd backend
python scripts/evaluate_recognition.py --dataset /data/lfw --pairs /data/lfw/pairs.txt \
  --out reports/lfw.json
```

Reports FAR/FRR/EER/accuracy over labelled genuine/impostor pairs plus embed latency percentiles.
No dataset ships with the repo and no accuracy number is claimed; the protocol, pair formats and
gating (`--min-accuracy`, `--max-eer`) are in [`evaluation.md`](evaluation.md).

## End-to-end: Playwright

```bash
cd frontend
npm run test:e2e             # starts the Next.js dev server on :3001 via webServer
npx playwright test --headed # watch it
PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test   # against an existing server
```

Specs live in `frontend/e2e/`. What is covered today and **what deliberately is not**:

- Covered: the app shell hydrates past the auth loading state and shows the public navigation;
  `/register` requires sign-in; `/student`, `/attendance`, `/classroom` and `/cctv` all render an
  auth-required state when signed out (no crash, no silent success).
- Covered without a session: `e2e/feature-logic.spec.ts` imports the pure helpers behind the
  signed-in UI — enrollment rejection → actionable checklist + metric formatting, consent
  staleness (including "unknown current notice never blocks"), and challenge copy (known and
  fallback names).
- Covered without a session: `e2e/a11y.spec.ts` runs axe-core on `/`, `/about`, `/contact` and
  `/register` and fails on critical/serious WCAG 2 A/AA findings. It is a floor, not a WCAG
  certification; signed-in screens still need the manual pass.
- **Not covered:** Google sign-in, the consent gate modal, the active-liveness toggle, role-aware
  navigation after login, attendance history rendering, and a real webcam liveness scan. Sign-in
  needs Firebase credentials; synthetic video is correctly rejected by the liveness service, so a
  faked camera would test the fake. These are manual checks below — an honest limitation, not
  something papered over with an always-pass mock.
- CI runs headless Chromium only; other engines are a local concern.

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
2. `/register` enrolls a real face (exactly one face enforced; consent notice visible). Deliberately
   enrol a blurry/dark frame first and confirm the checklist lists the right fixes and no row is
   created.
3. `/student`: live scan passes for the enrolled person, **fails** for a different person,
   and **fails** when the camera is covered with a photo.
4. Active liveness: enable the challenge toggle, perform it, and confirm a deliberately wrong
   action (e.g. no head turn) fails and records **no** attendance.
5. Consent gate: set a student row's `consent_version` to an older value, reload `/student`, and
   confirm the scan is blocked until the modal is accepted.
6. Attendance shows *verified* and *recorded* as separate states; repeat scan says
   "already recorded" and does not create a second row.
7. `/classroom` and `/cctv` refuse to start for a student account (403 surfaced as an error,
   not a broken page).
8. Deleting the profile removes photo + embedding + history and the student can re-enroll.

## CI

`.github/workflows/ci.yml` runs on every push and PR:

- frontend: `npm audit` → `lint` → `tsc` → `build`
- backend: `ruff check` → `pip-audit --local --skip-editable` (the environment just installed
  from `requirements-dev.txt`) → `pytest` → `alembic upgrade head` on a fresh SQLite DB
- secrets: gitleaks scan of the full history
- Playwright: headless Chromium, frontend started by the Playwright web server

A red check blocks the change. CI is a floor, not a ceiling — it never proves the camera path or
recognition accuracy.
