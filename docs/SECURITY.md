# Security model

> FaceSnap handles biometric data for students. Treat this document as a living checklist — it describes what is enforced today and what must stay true as the system evolves.

## Authentication

- Users sign in with Google via Firebase Auth. Every backend call attaches `Authorization: Bearer <ID token>` (see `frontend/lib/attendance.ts` → `authHeaders()`).
- `backend/app/auth.py` verifies tokens with `firebase-admin`. `REQUIRE_AUTH=false` is a **local-dev bypass only**; production must set `REQUIRE_AUTH=true` with `FIREBASE_SERVICE_ACCOUNT_JSON` configured.
- Camera devices without a user session can call `/api/pi/*` with `X-Service-Key: <PI_SERVICE_KEY>` instead.

## Authorization

- Roles: `admin` | `student` (stored on `users/{uid}`, default `student`).
- `/api/sync` requires `admin` or `operator`. Verification/detection routes require an authenticated user. The nav and pages hide staff tools from students, **but the backend re-checks everything** — UI gating is convenience, not control.
- Firestore rules (`frontend/firestore.rules`): users can only touch their own profile; students are owner-writable; attendance is create-only by the record owner with a strict allowlisted schema, immutable afterwards, admin-deletable.

## What the system guarantees

- **No fabricated identity** — CCTV/classroom only log backend-matched UIDs. Unknown faces and API failures produce review states and errors, never records.
- **No spoof-by-photo** (best effort) — 1:1 verification requires multi-frame liveness; failures return `match: false` with the liveness breakdown.
- **No key leakage** — the Groq key lives only in `GROQ_API_KEY` (server). The chatbot proxy (`/api/chat`) rate-limits (20 req/min/IP), allowlists models, caps input length, and times out at 25 s. **If a `NEXT_PUBLIC_GROQ_API_KEY` was ever deployed, rotate it** — it is compromised by design.
- **No oversized payloads** — 8 MB / 4096 px image caps plus pydantic field limits on every image-bearing route.

## Biometric data handling

- **Consent** — registration shows a biometric-use notice before capture.
- **Minimization** — embeddings (non-reversible vectors) are what matching uses; original photos are kept only where the product needs them.
- **Deletion** — students can delete their profile anytime from the student portal; `deleteAllFaceImages()` removes every Storage object under `faces/{uid}` recursively. Remember to also purge the Qdrant embedding (re-sync or delete by UID) — see deployment runbook.
- **Known gaps** (do not use real student records until closed): no duplicate-enrollment race guard beyond the client check, no retention-expiry job, student-doc reads expose face captures to any signed-in user. Track these as P0 before institutional rollout.

## Reporting issues

Open a private security advisory on GitHub (never a public issue) for suspected vulnerabilities. Include route, reproduction steps, and whether `REQUIRE_AUTH` was enabled.
