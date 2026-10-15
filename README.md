# FaceSnap

**Campus attendance, verified by face — not by trust.**

FaceSnap is an AI-powered attendance system for colleges and universities. Students enroll once with a guided face capture; then live verification, doorway batch mode, group-photo processing, and CCTV monitoring all match faces against enrolled embeddings — and only verified matches ever become attendance records.

Built with **Next.js 15 + Firebase** on the frontend and a **FastAPI + InsightFace ArcFace + Qdrant** recognition backend.

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
Google sign-in → student details → face capture → backend face check (exactly 1 face)
  → Firestore profile (+ face embedding synced to Qdrant vector DB)

Live scan (30 frames) → liveness analysis → ArcFace embedding → cosine-distance match
  → threshold check → canonical attendance event (once per session)
```

**Recognition pipeline:** InsightFace `buffalo_s` (ArcFace, 512-dim embeddings, cosine distance, threshold `0.35`) on ONNX Runtime · embeddings cached in Qdrant · liveness via rPPG + blink + motion scoring.

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
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Backend | Prod | Path to service-account credentials for token verification |
| `PI_SERVICE_KEY` | Backend | Prod (Pi) | Optional shared key letting cameras call `/api/pi/*` via `X-Service-Key` |
| `PI_CAMERA_ENABLED` | Backend | No | `true` to open the local camera for Pi endpoints (default `false`) |
| `QDRANT_PATH` | Backend | No | Vector DB storage path (`:memory:` default; set a directory for persistence) |
| `HOST` / `PORT` / `CORS_ORIGINS` | Backend | No | Server bind (`0.0.0.0`:`8000`) and allowed CORS origins |

## API reference

Base URL: `http://localhost:8000` (or your `PORT`). Authenticated routes expect `Authorization: Bearer <Firebase ID token>` (or `X-Service-Key` for camera endpoints when `PI_SERVICE_KEY` is set).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Welcome + engine info |
| GET | `/api/health` | — | Model readiness, vector-DB count, camera state (powers the dashboard status cards) |
| POST | `/api/verify` | User | 1:1 match: registered image vs live image |
| POST | `/api/verify_liveness` | User | 1:1 match over 5–60 frames with liveness analysis |
| POST | `/api/sync` | Admin/operator | Enroll up to 500 students' embeddings into Qdrant |
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

- **Firestore** (`frontend/firestore.rules`): users own their profile; students are owner-writable; attendance is create-only by the record owner (or admin) against a strict canonical schema — `studentUid, name, rollNumber, department, year, semester, timestamp, method` (+ optional `liveness_score`, `sessionId`). Deploy with `firebase deploy --only firestore:rules` from `frontend/`.
- **Storage**: face images live at `faces/{uid}/{timestamp}.jpg`; `deleteAllFaceImages()` removes every object recursively. Registration also keeps a base64 capture on the student doc for matching fallback.
- **Backend is the authority**: Firestore rules are the client boundary, but the API independently verifies ID tokens and roles on every route — Admin SDK writes bypass rules, so the backend never trusts them.
- **Privacy**: enrollment shows a biometric-consent notice; profiles (and therefore face data) can be deleted anytime from the student portal. See [`docs/SECURITY.md`](docs/SECURITY.md).

## Testing & CI

```bash
cd backend && python -m pytest -q        # matching-math unit tests (no model weights needed)
cd frontend && npm run lint              # ESLint
cd frontend && npx tsc --noEmit          # type check
cd frontend && npm run build             # production build
```

`.github/workflows/ci.yml` runs frontend lint + type-check + build and the backend test suite on every push/PR.

## Project structure

```
├── frontend/                 # Next.js 15 (React 19, TypeScript, Tailwind v4)
│   ├── app/                  # Routes: page (dashboard), register, student,
│   │                         #   classroom, cctv, attendance, about, contact, api/chat
│   ├── components/           # AuthProvider (role-aware), ThemeProvider/Toggle,
│   │                         #   Navigation (role-aware), Chatbot (via /api/chat), Footer
│   ├── lib/                  # firebase, attendance (canonical record builder + auth headers),
│   │                         #   storage, types, utils
│   └── firestore.rules       # Client security boundary
├── backend/                  # FastAPI recognition service
│   ├── app/auth.py           # Firebase ID-token verification + role/service-key gates
│   ├── app/routes/           # verification, detection, pi_routes
│   ├── app/services/         # face_service (ArcFace), liveness_service (rPPG/blink/motion),
│   │                         #   vector_service (Qdrant), camera (lifecycle + health)
│   ├── tests/                # pytest suite for matching math
│   └── desktop_app.py        # Legacy standalone Tkinter app (independent of the web stack)
├── docs/                     # Architecture, security, deployment guides
├── .github/workflows/ci.yml # Lint + type-check + build + tests
└── .env.example              # Environment template
```

## Deployment

- **Frontend** (Vercel / any Node host): `next.config.ts` uses `output: 'standalone'`. Set all `NEXT_PUBLIC_*` vars plus server-side `GROQ_API_KEY`.
- **Backend** (any Python host with ~2 GB RAM for models): `pip install -r requirements.txt`, provide `FIREBASE_SERVICE_ACCOUNT_JSON`, set `REQUIRE_AUTH=true`, `QDRANT_PATH` to a persistent volume, and run `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Full checklists in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## License

MIT
