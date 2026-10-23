# Deployment runbook

## Backend (recognition API + system of record)

1. Provision a host with Python 3.11+ and ~2 GB free RAM (InsightFace models) — CPU works, CUDA GPU is faster. Provision a managed Postgres instance for production.
2. `pip install -r backend/requirements.txt` and install the Postgres driver: `pip install "psycopg[binary]>=3.1"`.
3. Provide a Firebase service account (identity verification only) and set `FIREBASE_SERVICE_ACCOUNT_JSON=/run/secrets/firebase-service-account.json`.
4. Set production env (the app **refuses to start** if auth or CORS is unsafe):
   - `APP_ENV=production`
   - `REQUIRE_AUTH=true`
   - `DATABASE_URL=postgresql+psycopg://facesnap:<password>@<host>:5432/facesnap`
   - `FACE_IMAGE_DIR=/data/faces` (persistent volume — biometric originals)
   - `QDRANT_PATH=/data/qdrant` (persistent volume — otherwise embeddings vanish on restart)
   - `ADMIN_EMAILS=you@college.edu` (first admin; add more via the role endpoint afterwards)
   - `PI_CAMERA_ENABLED=true` (only on the Pi/camera host)
   - `PI_SERVICE_KEY=<long random string>` and share it with camera devices
   - `CORS_ORIGINS=https://your-frontend-domain` (explicit origins; `*` is rejected)
   - `RATE_LIMIT_PER_MINUTE=120` (tune for your expected scan volume)
   - `TRUST_PROXY_HEADERS=true` **only** if a reverse proxy you control overwrites `X-Forwarded-For`
   - `HOST=0.0.0.0`, `PORT=8000`
5. Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (use a process manager; one worker per GPU). `init_db()` creates tables and the sessionless-attendance partial unique index idempotently on first boot — introduce Alembic before your first schema change.
6. Smoke-test: `GET /api/health` → `face_model_ready: true`, `vector_db_ready: true`, `database_ready: true`, `environment: "production"`, `auth_required: true`. First boot downloads models — expect a slow start.
7. Enroll: sign in as an admin in the web app and register students. If the vector index was ever wiped, rebuild it from SQL with `POST /api/admin/backfill-embeddings` (no client data needed).

> SQLite (`DATABASE_URL=sqlite:///./facesnap.db`) is for local development only. It is single-writer; use Postgres when running more than one API worker.

## Frontend (Next.js)

1. `cd frontend && npm install`.
2. Set env: all `NEXT_PUBLIC_FIREBASE_*` (identity), `NEXT_PUBLIC_BACKEND_URL` (your API origin), server-side `GROQ_API_KEY` (+ optional `AI_MODEL`), and `NEXT_PUBLIC_APP_URL` (your public origin).
3. `npm run build` → deploy `.next/standalone` (Vercel, Docker, or any Node host).
4. There is no Firestore/Storage dependency: Firebase is used for Google sign-in only, and all application data lives in the backend database.

## Operational notes

- **Model cache**: `backend/app/.insightface/` is machine-local and git-ignored; warm it during deploy, not first request.
- **Embedding lifecycle**: enrollment indexes automatically; deletion removes the vector. Backfill is safe to re-run at any time — point IDs are deterministic, so entries update in place.
- **Monitoring**: poll `/api/health` (and `/api/pi/health` on camera hosts); alert on `face_model_ready: false`, `database_ready: false`, or camera `last_error`.
- **Backups**: nightly Postgres dumps, `FACE_IMAGE_DIR` volume snapshots, and Qdrant snapshots. SQL is the source of truth — Qdrant can always be rebuilt with a backfill.
- **Scaling**: API replicas are stateless except the camera lifecycle and the in-process rate limiter. Use one rate limiter instance per worker (or move it to Redis/edge) if you run multiple workers, and keep one recognition instance per camera on a private network with the service key.
- **Pi stream auth**: browsers cannot attach an `Authorization` header to an `<img>` MJPEG stream. With auth enabled, either terminate the stream at a trusted reverse proxy that injects the staff/service credential, or use `/api/pi/capture` + `/api/pi/detect` with normal authenticated `fetch` calls. Local development with `REQUIRE_AUTH=false` is unaffected.
- **Liveness caveat**: rPPG tuning is calibrated for typical webcams in reasonable light. Validate on your own hardware before relying on it for high-stakes attendance; it is not a certified PAD system.
- **Legacy data**: Firestore records from before the migration are not imported automatically. Teams that need them should export students and re-enroll faces through `POST /api/students/enroll`; attendance history can be loaded with a one-off SQL script.
