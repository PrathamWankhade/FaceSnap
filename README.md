# FaceSnap

**Campus attendance, verified by face — not by trust.**

FaceSnap is an AI-powered attendance system for colleges and universities. Students enroll once with a guided face capture; then live verification, doorway batch mode, group-photo processing, and CCTV monitoring all match faces against enrolled embeddings — and only verified matches ever become attendance records.

Built with **Next.js 15** on the frontend and a **FastAPI + SQL + InsightFace ArcFace + Qdrant** recognition backend. Firebase provides identity (Google SSO) only — the **relational database is the system of record**.

---

## Why FaceSnap?

- **Verified, not detected** — a face in frame means nothing until the backend matches it against an enrolled embedding *and* it passes liveness checks. Unknown faces go to a review queue, never into the register.
- **Liveness anti-spoofing** — multi-frame analysis (rPPG pulse signal, blink and motion cues) resists photo and video-replay attacks.
- **Four capture modes** — 1:1 student verification, live doorway batch, group-photo upload, and CCTV/Pi camera streams, all writing one canonical attendance schema.
- **No fake attendance, ever** — camera or API failures produce a visible error and zero records. Detection, recognition, and attendance are three separate, explicit states in the UI.
- **Secure by default** — Firebase ID-token auth on every backend route, role-aware UI *and* API enforcement, server-side chatbot proxy (no keys in the browser), and tight Firestore rules.

## How it works

```
Enroll        Verify / Attend
------        ----------------
Google sign-in → student details → face capture → backend validates exactly 1 face
  → student row + image in the local object store + ArcFace embedding in Qdrant
  → (all writes go through FastAPI; the browser never writes records directly)

Live scan (30 frames) → liveness analysis → ArcFace embedding → cosine-distance match
  → threshold check → idempotent attendance event (once per session, else per day/method)
```

**Recognition pipeline:** InsightFace `buffalo_s` (ArcFace, 512-dim embeddings, cosine distance, threshold `0.35`) on ONNX Runtime · embeddings cached in a persistent Qdrant index · liveness via rPPG + blink + motion scoring.

### Data layer

| Concern | Store |
|---------|-------|
| Identity (Google SSO) | Firebase Authentication — the only Firebase dependency left in the request path |
| Users, roles, students, courses, class sessions, attendance, leave, audit | SQLAlchemy relational DB — **SQLite for local dev**, Postgres via `DATABASE_URL` in production |
| Face embeddings | Qdrant (derived index, rebuildable with `POST /api/admin/backfill-embeddings`) |
| Enrollment photos | Local object store (`FACE_IMAGE_DIR`), only the key is stored in SQL |

The backend owns every write: enrollment, attendance, sessions, roles and leave requests. Attendance is **idempotent** — a unique `(student_id, session_id)` constraint plus a per-day/per-method check means retries and repeated CCTV frames never double-count a student.

## Quick start

### Prerequisites

- **Node.js** 20+ and **npm**
- **Python** 3.11+
- **Firebase project** with Authentication (Google), Firestore, and Storage enabled
- **Groq API key** (free, no credit card) at [console.groq.com](https://console.groq.com) — for the campus assistant chatbot

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

# 3. Environment — copy the template and fill in your values
cp ../.env.example ../frontend/.env.local
# (see Environment variables below)
```

### Run

```bash
# Terminal 1 — recognition API (default http://localhost:8000)
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — web app (http://localhost:3000)
cd frontend
npm run dev
```

Set `NEXT_PUBLIC_BACKEND_URL` in `frontend/.env.local` to wherever the API runs.

> First run downloads the InsightFace `buffalo_s` model pack (~a few hundred MB) into `backend/app/.insightface/` — this is cached locally and git-ignored.

## Environment variables

Copy `.env.example` to `frontend/.env.local` (frontend) and export backend-only values in the API's environment.

| Variable | Where | Required | Description |
|----------|-------|----------|-------------|
| `GROQ_API_KEY` | Backend / Next.js server | Yes (chatbot) | Groq key — **server-only, never `NEXT_PUBLIC_*`**. The browser calls `/api/chat`, which proxies securely. |
| `AI_MODEL` | Next.js server | No | Chat model allowlist default: `llama-3.3-70b-versatile` |
| `NEXT_PUBLIC_APP_URL` | Frontend | No | Frontend URL (default `http://localhost:3000`) |
| `NEXT_PUBLIC_FIREBASE_*` | Frontend | **Yes** | `PROJECT_ID`, `APP_ID`, `API_KEY`, `AUTH_DOMAIN`, `STORAGE_BUCKET`, `MESSAGING_SENDER_ID`, optional `MEASUREMENT_ID` |
| `NEXT_PUBLIC_BACKEND_URL` | Frontend | **Yes** | API base URL, e.g. `http://localhost:8000` |
| `REQUIRE_AUTH` | Backend | **Yes in prod** | `true` enforces Firebase ID-token verification on all API routes (`false` = local-dev bypass) |
| `DATABASE_URL` | Backend | No | SQLAlchemy DSN. Default `sqlite:///./facesnap.db`; use `postgresql+psycopg://…` in production |
| `FACE_IMAGE_DIR` | Backend | No | Directory for enrollment photos (default `./data/faces`). Mount a persistent volume in production |
| `ADMIN_EMAILS` | Backend | No | Comma-separated emails promoted to `admin` on first login |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Backend | Prod | Path to service-account credentials for token verification |
| `PI_SERVICE_KEY` | Backend | Prod (Pi) | Optional shared key letting cameras call `/api/pi/*` via `X-Service-Key` |
| `PI_CAMERA_ENABLED` | Backend | No | `true` to open the local camera for Pi endpoints (default `false`) |
| `QDRANT_PATH` | Backend | No | Qdrant storage path (default `./data/qdrant`, persistent). Use `:memory:` for an ephemeral index |
| `HOST` / `PORT` / `CORS_ORIGINS` | Backend | No | Server bind (`0.0.0.0`:`8000`) and allowed CORS origins |

## API reference

Base URL: `http://localhost:8000` (or your `PORT`). Authenticated routes expect `Authorization: Bearer <Firebase ID token>` (or `X-Service-Key` for camera endpoints when `PI_SERVICE_KEY` is set).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Welcome + engine/DB info |
| GET | `/api/health` | — | Model, DB and vector readiness, enrollment/attendance counts, camera state |
| GET | `/api/me` | User | Caller's role and student profile (from the database) |
| PATCH | `/api/users/{uid}/role` | Admin | Set a user's role (`admin` / `operator` / `student`) |
| POST | `/api/students/enroll` | User | Validate one face, store the photo, upsert the student row, index the embedding |
| GET | `/api/students` | User | Staff: all students; students: self only |
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
| POST | `/api/verify` | User | 1:1 match: registered image vs live image |
| POST | `/api/verify_liveness` | User | 1:1 match over 5–60 frames with liveness analysis |
| POST | `/api/sync` | Admin/operator | Legacy bulk embedding import (prefer enroll/backfill) |
| POST | `/api/detect_webcam` | User | Detect + recognize every face in a frame |
| GET | `/api/pi/health` | Camera caller | Pi camera + engine health |
| GET | `/api/pi/stream` | Camera caller | MJPEG camera stream |
| GET | `/api/pi/capture` | Camera caller | Still frame as base64 |
| GET | `/api/pi/detect` | Camera caller | Backend face detection + identity matching (unknown faces return `match: null` — never a guess) |

Backend config lives in `backend/app/config.py` — key knobs:

| Setting | Default | Meaning |
|---------|---------|---------|
| `ARCFACE_THRESHOLD` | `0.35` | Cosine-distance match threshold (lower = stricter) |
| `EMBEDDING_DIM` | `512` | ArcFace embedding size |
| `DETECTION_CONFIDENCE` | `0.5` | Face-detector confidence floor |
| `LIVENESS_SCORE_THRESHOLD` | `0.5` | Combined rPPG/blink/motion pass mark |
| `LIVENESS_RPPG_PASS` | `0.6` | A pulse this strong passes on its own (users who sit still / don't blink) |
| Image guardrails | 8 MB / 4096 px | Oversized or undecodable images are rejected with a clean error |

## App tour

| Route | Who | What |
|-------|-----|------|
| `/` | Everyone | Landing page, or a role-aware dashboard: student portal, staff operations, and live system-status cards |
| `/register` | Signed-in | 3-step enrollment: details → guided face capture (with biometric-consent notice) → confirmation. The backend must see exactly one face before the profile is saved |
| `/student` | Student | Personal info + live liveness scan. The result screen separates **Identity verified** from **Attendance recorded** — success is only claimed after the write confirms |
| `/classroom` | Staff | Doorway live mode (Start/Stop, engine + sync + detection toolbar, verified/review counters) and group-photo mode with per-student reviewable results |
| `/cctv` | Staff | Camera stream with Start/Pause/Stop, stream/engine/enrollment status chips, and a detection side panel — verified matches log once, unknowns wait for review |
| `/attendance` | Signed-in | Filterable history with method badges (`individual_live`, `doorway_batch`, `cctv_stream`, `upload`) |
| `/api/chat` | — | Server-side chatbot proxy: rate-limited, allowlisted models, 25 s timeout — the provider key never ships to the browser |

The UI ships in **light and dark themes** (toggle in the nav, persisted per device) with emerald = verified, amber = needs review, red = error.

## Data & security model

- **Relational system of record** (`backend/app/db.py`): `users`, `departments`, `courses`, `students`, `cameras`, `class_sessions`, `attendance`, `leave_requests`, `audit_log`. Real foreign keys mean attendance history survives profile edits; deleting a student cascades their attendance and removes their photo and vector.
- **Idempotent attendance**: a DB unique constraint on `(student_id, session_id)` plus a per-day/per-method lookup. Re-sending the same capture returns the existing record with `duplicate: true` instead of creating another row.
- **Role authority**: `users.role` in SQL is the source of truth; token claims are never trusted for authorization. `ADMIN_EMAILS` seeds the first admin, and `PATCH /api/users/{uid}/role` manages the rest.
- **Biometric privacy**: enrollment photos live in `FACE_IMAGE_DIR` (not in the database and never in Firestore); only the object key is stored. Students can delete their profile, photo, embedding and history at any time. Only the owner can fetch their own photo via `/api/students/me/face`.
- **Derived vector index**: Qdrant can be wiped and rebuilt from SQL at any time (`POST /api/admin/backfill-embeddings`). Embeddings are point IDs derived deterministically from the user id, so re-enrollment updates rather than duplicates.
- **Liveness**: static/repeated frames are rejected by a temporal-variance guard, preventing the previous false "pulse detected" result on still photos. See [`docs/SECURITY.md`](docs/SECURITY.md).
- **Legacy Firestore**: `frontend/firestore.rules` remains only for the optional role fallback and any historical data. New enrollments/attendance never touch it.

## Testing & CI

```bash
cd backend && python -m pytest -q        # registry/attendance/liveness tests (model stubbed, offline)
cd frontend && npm run lint              # ESLint
cd frontend && npx tsc --noEmit          # type check
cd frontend && npm run build             # production build
```

Backend tests cover attendance idempotency, session-scoped marks, role authority, enrollment upserts/conflicts, analytics and the liveness anti-spoofing guard. `.github/workflows/ci.yml` runs frontend lint + type-check + build and the backend test suite on every push/PR.

## Project structure

```
├── frontend/                 # Next.js 15 (React 19, TypeScript, Tailwind v4)
│   ├── app/                  # Routes: page (dashboard), register, student,
│   │                         #   classroom, cctv, attendance, about, contact, api/chat
│   ├── components/           # AuthProvider (role-aware), ThemeProvider/Toggle,
│   │                         #   Navigation (role-aware), Chatbot (via /api/chat), Footer
│   ├── lib/                  # api (backend client), firebase (identity), attendance
│   │                         #   (markAttendance + auth headers), types, utils
│   └── firestore.rules       # Legacy/optional role fallback
├── backend/                  # FastAPI recognition service
│   ├── app/db.py             # Relational schema (SQLAlchemy) — system of record
│   ├── app/auth.py           # Firebase token verification + DB-backed roles
│   ├── app/routes/           # registry (students/attendance/sessions), verification,
│   │                         #   detection, pi_routes
│   ├── app/services/         # face_service (ArcFace), liveness_service (rPPG/blink/motion),
│   │                         #   vector_service (Qdrant), image_store, camera
│   ├── tests/                # pytest: matching math, registry API, liveness
│   └── desktop_app.py        # Legacy standalone Tkinter app (independent of the web stack)
├── docs/                     # Architecture, security, deployment guides
├── .github/workflows/ci.yml # Lint + type-check + build + tests
└── .env.example              # Environment template
```

## Deployment

- **Frontend** (Vercel / any Node host): `next.config.ts` uses `output: 'standalone'`. Set all `NEXT_PUBLIC_*` vars plus server-side `GROQ_API_KEY`.
- **Backend** (any Python host with ~2 GB RAM for models): `pip install -r requirements.txt`, provide `FIREBASE_SERVICE_ACCOUNT_JSON`, set `REQUIRE_AUTH=true`, point `DATABASE_URL` at Postgres (install `psycopg[binary]`), set `QDRANT_PATH` and `FACE_IMAGE_DIR` to persistent volumes, and run `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Full checklists in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## License

MIT
