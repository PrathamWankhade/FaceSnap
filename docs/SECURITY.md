# Security model

> FaceSnap handles biometric data for students. Treat this document as a living checklist — it describes what is enforced today and what must stay true as the system evolves.

## Authentication

- Users sign in with Google via Firebase Auth. Every backend call attaches `Authorization: Bearer <ID token>` (see `frontend/lib/attendance.ts` → `authHeaders()`).
- `backend/app/auth.py` verifies tokens with `firebase-admin`. `REQUIRE_AUTH=false` is a **local-development bypass only**; it is loud in the logs and is refused in production.
- `APP_ENV=production` makes the backend **fail fast**: it will not start unless `REQUIRE_AUTH=true` and `CORS_ORIGINS` is an explicit allowlist. The bypass is also rejected at request time if the process is ever started in production with it enabled.
- Camera devices without a user session can call `/api/pi/*` with `X-Service-Key: <PI_SERVICE_KEY>` instead. The comparison uses a constant-time check.

## Authorization

- Roles: `admin` | `operator` | `student`, stored in the relational `users` table. **The database role is authoritative**; token claims are never used for authorization.
- New users default to `student`. Emails listed in `ADMIN_EMAILS` are promoted on first login; further changes require `PATCH /api/users/{uid}/role` by an admin.
- Enrollment, attendance and profile routes require an authenticated user. Staff endpoints (`/api/analytics/overview`, session creation, embedding backfill, `/api/sync`) require `admin`/`operator`.
- **Camera and matching endpoints are staff-only** (`/api/detect_webcam`, `/api/verify`, `/api/pi/*`) unless a valid service key is presented. Students cannot open the camera stream or use the backend as a general face-comparison oracle. The student flow uses `/api/verify_liveness` against their own enrolled template.
- Attendance is **idempotent at the database level**: a unique `(student_id, session_id)` constraint for session-scoped marks, plus a partial unique index on `(student_id, method, date(captured_at)) WHERE session_id IS NULL`. Application checks return a friendly `duplicate: true`; the index closes the concurrent-request race.
- A per-IP sliding-window limiter (`RATE_LIMIT_PER_MINUTE`, default 120/min) guards the expensive face/verification routes. It is in-process; multi-worker deployments should move it to Redis or the edge.

## What the system guarantees

- **No fabricated identity** — camera/classroom flows only log backend-matched UIDs. Unmatched faces and API failures produce review states and errors, never attendance records. The system does **not** claim a persistent review-queue workflow.
- **Best-effort anti-spoofing** — 1:1 verification requires multi-frame liveness. Static or repeated frames have zero temporal colour variation and are rejected before matching. rPPG uses a Haar-derived face region and the client's measured sample rate. A strong pulse can pass on its own; otherwise the combined score must clear the threshold. This is **not** a certified PAD system and has not been evaluated against a standard spoof corpus.
- **No key leakage** — the Groq key lives only in `GROQ_API_KEY` (server). The chatbot proxy (`/api/chat`) rate-limits (20 req/min/IP), allowlists models, caps input length, and times out at 25 s. **If a `NEXT_PUBLIC_GROQ_API_KEY` was ever deployed or committed, rotate it** — it is compromised by design. The local key was renamed to `GROQ_API_KEY`; rotation at the provider is still recommended.
- **No oversized payloads** — 8 MB / 4096 px image caps plus pydantic field limits on every image-bearing route (including each liveness frame).

## Biometric data handling

- **Consent** — registration shows a biometric-use notice before capture.
- **Minimization** — matching uses non-reversible embeddings. Enrollment originals are stored in `FACE_IMAGE_DIR` (outside the database), referenced only by a key; they are never exposed in list/profile responses. `GET /api/students/me/face` is owner-only and exists solely so the verification screen can compare the live capture.
- **Deletion** — `DELETE /api/students/{id}` (owner or admin) removes the student row, cascades attendance/leave, deletes the stored photo and removes the Qdrant vector in one request.
- **Role separation** — list responses contain academic data only; staff never receive another student's photo through the API.
- **Known gaps** (do not use real student records until closed): no automated retention-expiry job, no independent audit of the rPPG calibration across devices/cameras, and no schema-migration tool (Alembic) yet. Re-enrollment replaces a photo rather than keeping a version history.

## Reporting issues

Open a private security advisory on GitHub (never a public issue) for suspected vulnerabilities. Include route, reproduction steps, and whether `REQUIRE_AUTH` was enabled.
