# FaceSnap

**Campus attendance, verified by face — not by trust.**

FaceSnap is a full-stack attendance system for colleges and universities. Students enroll once with a guided face capture; live verification, doorway batch mode, group-photo processing, and a single-camera stream then match faces against enrolled embeddings — and only verified matches become attendance records.

Built with **Next.js 15** on the frontend and a **FastAPI + SQL + InsightFace ArcFace + Qdrant** recognition backend. Firebase provides identity (Google SSO) only — the **relational database is the system of record**.

---

## Why FaceSnap?

- **Verified, not detected** — a face in frame means nothing until the backend matches it against an enrolled embedding *and* liveness checks pass. Unmatched faces are surfaced as review items and are never written to attendance.
- **Multi-signal liveness (best effort)** — rPPG pulse, blink and motion cues over a ~5-second frame burst. Static frames are rejected outright. This raises the cost of simple photo/replay attacks; it is **not** a certified presentation-attack-detection (PAD) system.
- **Four capture modes** — 1:1 student verification, live doorway batch, group-photo upload, and a single-camera stream (Pi/webcam), all writing one canonical attendance schema.
- **Failures are visible** — camera or API failures produce an error and zero records. Detection, recognition, and attendance are three separate, explicit states in the UI.
- **Safe production defaults** — Firebase ID-token auth, role-aware UI *and* API enforcement, staff-only camera/matching routes, a server-side chatbot proxy (no provider key in the browser), explicit CORS, and a fail-fast startup guard.

## How it works

```
Enroll        Verify / Attend
------        ----------------
Google sign-in → student details → face capture → backend validates exactly 1 face
  → student row + image in the local image store + ArcFace embedding in Qdrant
  → (all writes go through FastAPI; the browser never writes records directly)

Live scan (~50 frames at ~10 FPS) → liveness analysis → ArcFace embedding → cosine-distance match
  → threshold check → idempotent attendance event (once per session, else per day/method)
```

**Recognition pipeline:** InsightFace `buffalo_s` (ArcFace, 512-dim embeddings, cosine distance, threshold `0.35`) on ONNX Runtime · embeddings cached in a persistent Qdrant index · liveness via rPPG + blink + motion scoring.

### Data layer

| Concern | Store |
|---------|-------|
| Identity (Google SSO) | Firebase Authentication — the only Firebase dependency left in the request path |
| Users, roles, students, courses, class sessions, attendance, leave, audit | SQLAlchemy relational DB — **SQLite for local dev**, Postgres via `DATABASE_URL` in production |
| Face embeddings | Qdrant (derived index, rebuildable with `POST /api/admin/backfill-embeddings`) |
| Enrollment photos | Local image store (`FACE_IMAGE_DIR`), only the key is stored in SQL |

The backend owns every write: enrollment, attendance, sessions, roles and leave requests. Attendance is **idempotent** — a unique `(student_id, session_id)` constraint for session-scoped marks, plus a partial unique index on `(student_id, method, date(captured_at))` for sessionless marks. Retries, repeated camera frames, and concurrent requests cannot double-count a student.

## Quick start

### Prerequisites

- **Node.js** 20+ and **npm**
- **Python** 3.11+
- **Firebase project** with Authentication → Google enabled (identity only; no Firestore or Storage required)
- **Groq API key** (optional, free) at [console.groq.com](https://console.groq.com) — for the campus-assistant chatbot

### Setup

```bash
# 1. Frontend dependencies
cd frontend && npm install

# 2. Backend dependencies
cd ../backend
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 3. Environment
#    Frontend: copy frontend/.env.example -> frontend/.env.local
#    Backend:  copy backend/.env.example  -> backend/.env
```

For a local-only run, leave `REQUIRE_AUTH=false` in `backend/.env` (the development bypass). For anything reachable from another machine, see [Production](#production).

### Run

```bash
# Terminal 1 — recognition API (default http://localhost:8000)
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — web app (default http://localhost:3000)
cd frontend
npm run dev
```

Set `NEXT_PUBLIC_BACKEND_URL` in `frontend/.env.local` to wherever the API runs. If port 3000 is taken, run `npm run dev -- -p 3001` and update `NEXT_PUBLIC_APP_URL` / `CORS_ORIGINS` accordingly.

> First run downloads the InsightFace `buffalo_s` model pack (~a few hundred MB) into `backend/app/.insightface/` — this is cached locally and git-ignored.

## Environment variables

Copy `frontend/.env.example` → `frontend/.env.local` and `backend/.env.example` → `backend/.env`. The backend loads `backend/.env` with `python-dotenv`; real environment variables always win.

| Variable | Where | Required | Description |
|----------|-------|----------|-------------|
| `GROQ_API_KEY` | Next.js server | No (chatbot) | Groq key — **server-only, never `NEXT_PUBLIC_*`**. The browser calls `/api/chat`, which proxies securely. |
| `AI_MODEL` | Next.js server | No | Chat model allowlist default: `llama-3.3-70b-versatile` |
| `NEXT_PUBLIC_APP_URL` | Frontend | No | Frontend URL (default `http://localhost:3000`) |
| `NEXT_PUBLIC_FIREBASE_*` | Frontend | **Yes** | `PROJECT_ID`, `APP_ID`, `API_KEY`, `AUTH_DOMAIN`, `MESSAGING_SENDER_ID`, optional `MEASUREMENT_ID` |
| `NEXT_PUBLIC_BACKEND_URL` | Frontend | **Yes** | API base URL, e.g. `http://localhost:8000` |
| `APP_ENV` | Backend | No | `development` (default) or `production`. Production enables fail-fast checks. |
| `REQUIRE_AUTH` | Backend | **Yes in prod** | `true` verifies Firebase ID tokens. Defaults to `true` when `APP_ENV=production`, `false` otherwise. Production refuses to boot with the bypass enabled. |
| `CORS_ORIGINS` | Backend | **Yes in prod** | Comma-separated browser origins. Development defaults to `*`; production requires explicit origins. |
| `RATE_LIMIT_PER_MINUTE` | Backend | No | Per-IP limit for face/verification routes (default `120`, `0` disables). In-memory per worker. |
| `TRUST_PROXY_HEADERS` | Backend | No | Trust `X-Forwarded-For` for client IPs. Keep `false` unless a proxy you control overwrites the header. |
| `DATABASE_URL` | Backend | No | SQLAlchemy DSN. Default `sqlite:///./facesnap.db`; use `postgresql+psycopg://…` in production |
| `FACE_IMAGE_DIR` | Backend | No | Directory for enrollment photos (default `./data/faces`). Mount a persistent volume in production |
| `ADMIN_EMAILS` | Backend | No | Comma-separated emails promoted to `admin` on first login |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Backend | Prod | Path to service-account credentials for token verification |
| `PI_SERVICE_KEY` | Backend | Prod (Pi) | Shared key letting camera devices call `/api/pi/*` via `X-Service-Key` |
| `PI_CAMERA_ENABLED` | Backend | No | `true` to open the local camera for Pi endpoints (default `false`) |
| `QDRANT_PATH` | Backend | No | Qdrant storage path (default `./data/qdrant`, persistent). Use `:memory:` for an ephemeral index |
| `HOST` / `PORT` | Backend | No | Server bind (default `0.0.0.0:8000`) |

## API reference

Base URL: `http://localhost:8000` (or your `PORT`). Authenticated routes expect `Authorization: Bearer <Firebase ID token>`. Camera endpoints accept a staff user **or** `X-Service-Key: <PI_SERVICE_KEY>`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Welcome + engine/DB info |
| GET | `/api/health` | — | Model, DB and vector readiness, enrollment/attendance counts, camera state |
| GET | `/api/me` | User | Caller's role and student profile (from the database) |
| PATCH | `/api/users/{uid}/role` | Admin | Set a user's role (`admin` / `operator` / `student`) |
| POST | `/api/students/enroll` | User | Validate one face, store the photo, upsert the student row, index the embedding |
| GET | `/api/students` | Staff | All students. Students get their own profile via `/api/students/me` |
| GET | `/api/students/me` | User | Caller's student profile |
| GET | `/api/students/me/face` | User | Caller's own enrollment photo (owner-only data URL) |
| DELETE | `/api/students/{id}` | Owner/Admin | Delete profile, photo, embedding and attendance |
| POST | `/api/attendance` | User | Record attendance (idempotent). Staff may pass `student_uid` |
| GET | `/api/attendance` | User | History with `student_uid`, `method`, `session_id`, `from`, `to`, `limit` filters |
| GET | `/api/attendance/summary` | User | Per-day totals + method breakdown for the last N days |
| GET | `/api/analytics/overview` | Staff | Students, today/7-day attendance, methods, departments, cameras |
| POST/GET | `/api/sessions` | Staff / User | Create and list class sessions |
| POST/GET | `/api/leave` | User | Submit and list leave requests |
| POST | `/api/admin/backfill-embeddings` | Admin | Rebuild the Qdrant index from stored enrollment photos |
| POST | `/api/verify` | **Staff** | 1:1 match: registered image vs live image (staff-only; avoids a general face-comparison oracle) |
| POST | `/api/verify_liveness` | User | 1:1 match over 5–60 frames with liveness; send `frame_interval_ms` so rPPG uses the measured sample rate |
| POST | `/api/sync` | Admin/operator | Bulk embedding import (legacy; prefer enroll/backfill) |
| POST | `/api/detect_webcam` | **Staff** | Detect + recognize every face in a frame |
| GET | `/api/pi/health` | Staff/Service | Pi camera + engine health |
| GET | `/api/pi/stream` | Staff/Service | MJPEG camera stream |
| GET | `/api/pi/capture` | Staff/Service | Still frame as base64 |
| GET | `/api/pi/detect` | Staff/Service | Face detection + identity matching (unknown faces return `match: null` — never a guess) |

Backend config lives in `backend/app/config.py` — key knobs:

| Setting | Default | Meaning |
|---------|---------|---------|
| `ARCFACE_THRESHOLD` | `0.35` | Cosine-distance match threshold (lower = stricter) |
| `EMBEDDING_DIM` | `512` | ArcFace embedding size |
| `DETECTION_CONFIDENCE` | `0.5` | Face-detector confidence floor |
| `LIVENESS_SCORE_THRESHOLD` | `0.5` | Combined rPPG/blink/motion pass mark |
| `LIVENESS_RPPG_PASS` | `0.6` | A pulse this strong passes on its own (users who sit still / don't blink) |
| `LIVENESS_FPS_TARGET` | `10` | Fallback sample rate when a client omits `frame_interval_ms` |
| Image guardrails | 8 MB / 4096 px | Oversized or undecodable images are rejected with a clean error |

## App tour

| Route | Who | What |
|-------|-----|------|
| `/` | Everyone | Landing page, or a role-aware dashboard: student portal, staff operations, and live system-status cards |
| `/register` | Signed-in | 3-step enrollment: details → guided face capture (with biometric-consent notice) → confirmation. The backend must see exactly one face before the profile is saved |
| `/student` | Student | Personal info + live liveness scan (~5 s). The result screen separates **Identity verified** from **Attendance recorded** — success is only claimed after the write confirms |
| `/classroom` | Staff | Doorway live mode (Start/Stop, engine + sync + detection toolbar, verified/review counters) and group-photo mode with per-student reviewable results |
| `/cctv` | Staff | Single-camera stream with Start/Pause/Stop, stream/engine/enrollment status chips, and a detection side panel — verified matches log once, unmatched faces wait for review |
| `/attendance` | Signed-in | Filterable history with method badges (`individual_live`, `doorway_batch`, `cctv_stream`, `upload`) |
| `/api/chat` | — | Server-side chatbot proxy: rate-limited, allowlisted models, 25 s timeout — the provider key never ships to the browser |

The UI ships in **light and dark themes** (toggle in the nav, persisted per device) with emerald = verified, amber = needs review, red = error.

## Data & security model

- **Relational system of record** (`backend/app/db.py`): `users`, `departments`, `courses`, `students`, `cameras`, `class_sessions`, `attendance`, `leave_requests`, `audit_log`. Real foreign keys mean attendance history survives profile edits; deleting a student cascades their attendance and removes their photo and vector.
- **Idempotent attendance**: a DB unique constraint on `(student_id, session_id)`, plus a partial unique index for sessionless marks (`student_id`, `method`, `date(captured_at)` where `session_id IS NULL`). Re-sending the same capture returns the existing record with `duplicate: true`.
- **Role authority**: `users.role` in SQL is the source of truth; token claims are never trusted for authorization. `ADMIN_EMAILS` seeds the first admin, and `PATCH /api/users/{uid}/role` manages the rest.
- **Staff-only camera/matching**: `/api/detect_webcam`, `/api/verify`, and `/api/pi/*` require `admin`/`operator` (or a valid `PI_SERVICE_KEY`). Attendance tracking itself stays available to authenticated students.
- **Biometric privacy**: enrollment photos live in `FACE_IMAGE_DIR` (not in the database and never in Firebase); only the object key is stored. Students can delete their profile, photo, embedding and history at any time. Only the owner can fetch their own photo via `/api/students/me/face`.
- **Derived vector index**: Qdrant can be wiped and rebuilt from SQL at any time (`POST /api/admin/backfill-embeddings`). Embedding point IDs are derived deterministically from the user id, so re-enrollment updates rather than duplicates.
- **Liveness**: static/repeated frames are rejected by a temporal-variance guard. rPPG runs on a Haar-derived face region at the client's measured FPS. See [`docs/SECURITY.md`](docs/SECURITY.md).
- **Production guard**: with `APP_ENV=production`, startup fails if `REQUIRE_AUTH` is off or CORS is a wildcard. The development auth bypass is also refused at request time in production.
- **Rate limits**: face/verification routes use a small in-process sliding window (`RATE_LIMIT_PER_MINUTE`). Multi-worker deployments should move this to Redis.

### Limitations (honest scope)

- Liveness is **best-effort**, not certified PAD. It is not evaluated against a standard spoof corpus and does not claim resistance to high-quality deepfakes or professional replay setups.
- Recognition accuracy depends on enrollment photo quality, lighting, and camera placement. No LFW/benchmark number is claimed for this deployment.
- `/cctv` consumes a single camera stream (Pi or webcam); it is **not** an RTSP/CCTV fleet integration. With auth enabled, the browser's `<img>` stream cannot attach a bearer header — use a trusted proxy or the authenticated capture/detect endpoints.
- SQLite is for local development. Multi-worker production requires Postgres and a shared rate-limit store.
- There is no retention-expiry job and no schema-migration tool (Alembic) yet — `init_db()` creates tables, and the partial index is added idempotently on startup.
- The in-process rate limiter and Qdrant local mode are single-node conveniences.

## Testing & CI

```bash
cd backend && python -m pytest -q        # registry/attendance/liveness/security tests (model stubbed, offline)
cd frontend && npm run lint              # ESLint
cd frontend && npx tsc --noEmit          # type check
cd frontend && npm run build             # production build
```

Backend tests cover attendance idempotency (including the DB-level index), session-scoped marks, role authority, enrollment upserts/conflicts, analytics, liveness sampling/FPS handling, production config guards, and staff-only access. `.github/workflows/ci.yml` runs frontend lint + type-check + build and the backend test suite on every push/PR.

## Project structure

```
├── frontend/                 # Next.js 15 (React 19, TypeScript, Tailwind v4)
│   ├── app/                  # Routes: page (dashboard), register, student,
│   │                         #   classroom, cctv, attendance, about, contact, api/chat
│   ├── components/           # AuthProvider (role-aware), ThemeProvider/Toggle,
│   │                         #   Navigation (role-aware), Chatbot (via /api/chat), Footer
│   ├── lib/                  # api (backend client), firebase (identity only), attendance,
│   │                         #   overlay (object-fit mapping), types, utils
│   └── .env.example          # Frontend environment template
├── backend/                  # FastAPI recognition service
│   ├── app/db.py             # Relational schema (SQLAlchemy) — system of record
│   ├── app/auth.py           # Firebase token verification + DB-backed roles
│   ├── app/rate_limit.py     # Sliding-window limiter for face endpoints
│   ├── app/routes/           # registry (students/attendance/sessions), verification,
│   │                         #   detection, pi_routes
│   ├── app/services/         # face_service (ArcFace), liveness_service (rPPG/blink/motion),
│   │                         #   vector_service (Qdrant), image_store, camera
│   ├── tests/                # pytest: matching math, registry API, liveness, security
│   └── .env.example          # Backend environment template
├── docs/                     # Architecture, security, deployment guides
├── .github/workflows/ci.yml  # Lint + type-check + build + tests
└── LICENSE                   # MIT
```

## Production

- **Frontend** (Vercel / any Node host): `next.config.ts` uses `output: 'standalone'`. Set all `NEXT_PUBLIC_*` vars plus server-side `GROQ_API_KEY`.
- **Backend** (any Python host with ~2 GB RAM for models):
  - `APP_ENV=production` and `REQUIRE_AUTH=true` (the app refuses to start otherwise).
  - `CORS_ORIGINS=https://your-frontend.example` (explicit origins — no `*`).
  - `FIREBASE_SERVICE_ACCOUNT_JSON` pointing at a service-account file.
  - `DATABASE_URL=postgresql+psycopg://…` (install `psycopg[binary]`), persistent `QDRANT_PATH` and `FACE_IMAGE_DIR`.
  - `PI_SERVICE_KEY` if camera devices call the API directly.
  - Run `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Full checklists in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## License

MIT — see [`LICENSE`](LICENSE).
