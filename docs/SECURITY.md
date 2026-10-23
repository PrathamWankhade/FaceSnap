# Security model

> FaceSnap handles biometric data for students. Treat this document as a living checklist — it describes what is enforced today and what must stay true as the system evolves.

## Authentication

- Users sign in with Google via Firebase Auth. Every backend call attaches `Authorization: Bearer <ID token>` (see `frontend/lib/attendance.ts` → `authHeaders()`).
- `backend/app/auth.py` verifies tokens with `firebase-admin`. `REQUIRE_AUTH=false` is a **local-dev bypass only**; production must set `REQUIRE_AUTH=true` with `FIREBASE_SERVICE_ACCOUNT_JSON` configured.
- Camera devices without a user session can call `/api/pi/*` with `X-Service-Key: <PI_SERVICE_KEY>` instead.

## Authorization

- Roles: `admin` | `operator` | `student`, stored in the relational `users` table. **The database role is authoritative**; token claims are never used for authorization.
- New users default to `student`. Emails listed in `ADMIN_EMAILS` are promoted on first login; further changes require `PATCH /api/users/{uid}/role` by an admin.
- Enrollment, attendance and profile routes require an authenticated user. Staff endpoints (`/api/analytics/overview`, session creation, embedding backfill, `/api/sync`) require `admin`/`operator`. Students can only see and write their own records — the backend re-checks every request, so UI gating is convenience, not control.
- Attendance is **idempotent at the database level**: a unique `(student_id, session_id)` constraint plus a per-day/per-method check prevents duplicate records from retries, repeated CCTV frames, or concurrent requests.

## What the system guarantees

- **No fabricated identity** — CCTV/classroom only log backend-matched UIDs. Unknown faces and API failures produce review states and errors, never records.
- **No spoof-by-photo** (best effort) — 1:1 verification requires multi-frame liveness. Static or repeated frames have zero temporal colour variation and are rejected before matching. A strong pulse can pass on its own; otherwise the combined score must clear the threshold.
- **No key leakage** — the Groq key lives only in `GROQ_API_KEY` (server). The chatbot proxy (`/api/chat`) rate-limits (20 req/min/IP), allowlists models, caps input length, and times out at 25 s. **If a `NEXT_PUBLIC_GROQ_API_KEY` was ever deployed, rotate it** — it is compromised by design.
- **No oversized payloads** — 8 MB / 4096 px image caps plus pydantic field limits on every image-bearing route.

## Biometric data handling

- **Consent** — registration shows a biometric-use notice before capture.
- **Minimization** — matching uses non-reversible embeddings. Enrollment originals are stored in `FACE_IMAGE_DIR` (outside the database), referenced only by a key; they are never exposed in list/profile responses. `GET /api/students/me/face` is owner-only and exists solely so the verification screen can compare the live capture.
- **Deletion** — `DELETE /api/students/{id}` (owner or admin) removes the student row, cascades attendance/leave, deletes the stored photo and removes the Qdrant vector in one request.
- **Role separation** — list responses contain academic data only; staff never receive another student's photo through the API.
- **Known gaps** (do not use real student records until closed): no automated retention-expiry job, and no independent audit of the rPPG calibration across devices/cameras. Re-enrollment replaces a photo rather than keeping a version history.

## Reporting issues

Open a private security advisory on GitHub (never a public issue) for suspected vulnerabilities. Include route, reproduction steps, and whether `REQUIRE_AUTH` was enabled.
