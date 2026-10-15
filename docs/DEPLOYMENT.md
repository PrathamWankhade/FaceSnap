# Deployment runbook

## Backend (recognition API)

1. Provision a host with Python 3.11+ and ~2 GB free RAM (InsightFace models) — CPU works, CUDA GPU is faster.
2. `pip install -r backend/requirements.txt`.
3. Provide a Firebase service account and export `FIREBASE_SERVICE_ACCOUNT_JSON=/run/secrets/firebase-service-account.json`.
4. Set production env:
   - `REQUIRE_AUTH=true`
   - `QDRANT_PATH=/data/qdrant` (persistent volume — otherwise embeddings vanish on restart)
   - `PI_CAMERA_ENABLED=true` (only on the Pi/camera host)
   - `PI_SERVICE_KEY=<long random string>` and share it with camera devices
   - `CORS_ORIGINS=https://your-frontend-domain`
   - `HOST=0.0.0.0`, `PORT=8000`
5. Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (use a process manager; 1 worker per GPU).
6. Smoke-test: `GET /api/health` → `face_model_ready: true`, `vector_db_ready: true`. First boot downloads models — expect a slow start.
7. Enroll: sign in as an admin in the web app, register students, then trigger a sync from the classroom page (or `POST /api/sync`).

## Frontend (Next.js)

1. `cd frontend && npm install`.
2. Set env: all `NEXT_PUBLIC_FIREBASE_*`, `NEXT_PUBLIC_BACKEND_URL` (your API origin), server-side `GROQ_API_KEY` (+ optional `AI_MODEL`).
3. `npm run build` → deploy `.next/standalone` (Vercel, Docker, or any Node host).
4. Deploy Firestore rules from `frontend/`: `firebase deploy --only firestore:rules`. Re-deploy rules on every rules change — the console copy can drift.

## Operational notes

- **Model cache**: `backend/app/.insightface/` is machine-local and git-ignored; warm it during deploy, not first request.
- **Embedding deletion**: after deleting a student profile, remove their vector — call Qdrant delete by UID payload or re-run a full `/api/sync` with the current roster.
- **Monitoring**: poll `/api/health` (and `/api/pi/health` on camera hosts); alert on `face_model_ready: false` or camera `last_error`. The web dashboard surfaces the same status cards.
- **Backups**: Firestore scheduled backups + Storage versioning for `faces/`; Qdrant snapshots if `QDRANT_PATH` is file-backed (in-memory mode needs a re-sync after every restart).
- **Scaling**: the API is stateless except Qdrant/camera — scale web replicas freely, keep one recognition instance per camera, and put cameras on a private network with the service key.
