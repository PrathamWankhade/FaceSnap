# System Design

Status: approved (2026-10). Owner: FaceSnap maintainers.
Companion docs: [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`permissions.md`](permissions.md) ·
[`decisions/`](decisions/) · [`SECURITY.md`](SECURITY.md)

## 1. Problem

Colleges take attendance by hand (roll call), by proxy (a friend answers), or by student-operated
apps that trust the client. All three are spoofable, and none of them produce evidence when an
attendance record is disputed.

**FaceSnap's thesis:** an attendance row should be *earned* — a server-side match against an
enrolled face, with a liveness signal — and should carry the evidence needed to defend it
(method, liveness score, match distance, actor, timestamp).

## 2. Personas

| Persona | Context | Needs | Fails when |
|---------|---------|-------|-----------|
| **Student** (primary) | 18–24, phone or laptop, walking into a lecture hall on 4G/campus Wi-Fi | Enroll once (< 2 min), mark attendance in one tap, see own history, delete own biometric data | Camera permission loops, "already marked" confusion, a green screen that did not actually write a row |
| **Operator / teacher** (staff) | At a doorway or desk PC during class change | Start a scan, see who is verified vs. needs review *while people walk past*, fix a miss, export history | Silent failures, unclear whether a frame was dropped, no way to see engine health |
| **Admin** | College IT / department admin | Manage roles, maintain the enrollment list, rebuild the index, trust that roles are enforced server-side | An operator or student who can escalate their own role; data loss with no restore path |
| **Maintainer (you/me)** | The developer running this repo | Ship a change safely, know what broke, roll back, answer "is it up?" | Undocumented state, no migration path, a green CI that does not test the risky thing |

## 3. Scope

### In scope (v1)

- One institution. Three roles: `admin`, `operator`, `student`.
- Google SSO (Firebase identity) + DB-backed role assignment.
- Enrollment: one face photo → student row + image store + ArcFace embedding.
- Four capture modes: 1:1 live verification, doorway batch, group-photo upload, single camera stream.
- Attendance: idempotent writes, session-scoped or per-day, full history with filters.
- Class sessions, leave requests, analytics overview, audit log.
- Liveness best-effort (rPPG + blink + motion) on the 1:1 flow.
- Consent notice at enrollment, self-service deletion of profile/photo/embedding/history.

### Out of scope (explicitly, with the reason)

| Not built | Why |
|-----------|-----|
| Multi-tenancy / organizations | Single institution is the actual product. Tenancy would change every query, permission and test for a hypothetical second customer → [`decisions/0002`](decisions/0002-multi-tenancy.md) |
| Billing, plans, quotas | No paying customer and no metering story; would be theatre → [`decisions/0003`](decisions/0003-billing-out-of-scope.md) |
| RTSP/CCTV fleet, NVR integration | The `/cctv` screen drives **one** camera. Fleet integration is a different product with a different threat model |
| Certified presentation-attack detection | Would require a spoof corpus, a PAD-certified model and an evaluation harness we do not have. Liveness is advertised as best-effort |
| Mobile apps | Responsive web covers the student flow; apps change the release pipeline, not the value |
| Offline-first attendance | Conflict resolution on reconnect is a large design surface; campus Wi-Fi assumption holds for v1 |
| Live proctoring / exam surveillance | Different consent, retention and legal posture |

## 4. Non-functional requirements

These are the acceptance criteria the ops/CI layers below exist to satisfy.

### Correctness
- **NFR-C1** An attendance row is written only by the backend after a server-side match.
- **NFR-C2** The same student cannot be double-counted for the same session, or for the same
  method on the same day, even under concurrent requests. Enforced **in the database**, not just
  in application code.
- **NFR-C3** Qdrant and the image store can be destroyed and rebuilt from SQL
  (`POST /api/admin/backfill-embeddings`) with no data loss.

### Security
- **NFR-S1** Every non-public endpoint returns `401` with no/invalid token; `403` when the role is
  wrong. No endpoint returns 200 to a student because of a missing guard.
- **NFR-S2** Production refuses to boot with the auth bypass on or a wildcard CORS origin.
- **NFR-S3** A student cannot read another student's profile, photo, attendance or leave rows
  (no IDOR), by ID or by query parameter.
- **NFR-S4** No provider/API key is ever shipped to the browser.
- **NFR-S5** Dependency vulnerabilities and leaked secrets are caught in CI, not in production.

### Privacy
- **NFR-P1** Biometric originals live in the image store, never in the DB and never in a
  third-party analytics store. Only the object key is in SQL.
- **NFR-P2** A student can delete their profile, photo, embedding and attendance; deletion is
  cascading and audited.
- **NFR-P3** Enrollment requires an explicit consent acknowledgement in the UI.

### Availability & operability
- **NFR-O1** `/api/health/live` answers `200` while the process is up; `/api/health` reports
  per-component readiness (`database`, `vector`, `face_model`, `camera`).
- **NFR-O2** Every request carries a correlation ID, returned in a response header and attached
  to every log line and error.
- **NFR-O3** Logs are structured JSON in production and carry no tokens, keys or image bytes.
- **NFR-O4** A backup exists, is automated, and has been **restored at least once into a clean
  environment**. An untested backup is not a backup.
- **NFR-O5** Schema changes are versioned migrations; `alembic upgrade head` is the only supported
  way to change production schema.

### Performance
- **NFR-F1** Health endpoints answer in < 100 ms without touching the model.
- **NFR-F2** Recognition endpoints are rate-limited per client (`RATE_LIMIT_PER_MINUTE`).
- **NFR-F3** The UI never blocks the camera loop on a non-critical request; detection overlay
  stays responsive on a 1080p stream.

### Quality
- **NFR-Q1** CI is green on `main`: lint, type-check, build, pytest, ruff, dependency audit.
- **NFR-Q2** Every permission change ships with a 401/403/cross-user test.
- **NFR-Q3** Public claims match tested behaviour (README Limitations must stay honest).

## 5. Core flows

```
Enrollment      POST /api/students/enroll
                guardrails (8 MB / 4096 px, exactly 1 face)
                -> students row -> image_store.save() -> Qdrant upsert -> audit row

Verification    POST /api/verify_liveness  (frames + measured frame_interval_ms)
                liveness (rPPG/blink/motion on a Haar ROI)
                -> ArcFace embed of frames -> cosine distance <= 0.35
                -> verified? -> client POSTs /api/attendance
                -> idempotency check + partial unique index -> audit row

Camera stream   GET  /api/pi/detect  (staff or X-Service-Key)
                -> match or null (never a guess) -> UI review queue -> attendance
```

**Verified ≠ recorded.** The UI shows these as two separate states; success is only claimed after
the attendance write confirms (`duplicate: true` counts as recorded, not as a second mark).

## 6. Failure behaviour (what we promise when things break)

| Failure | Behaviour |
|---------|-----------|
| Face model not loaded | Endpoints return `503` with a clear message; health shows `face_model_ready: false`; nothing silently succeeds |
| Vector index down | Enrollment still writes SQL; `embedding_indexed: false` is surfaced; rebuild later |
| Attendance race | Second writer gets `409`/`duplicate: true`, never a second row |
| Invalid/expired token | `401`, UI prompts re-auth; no partial write |
| Wrong role | `403`, audited route, no information leak about other rows |
| Client sends still frames as liveness | Rejected (`live: false`) with the measured FPS in the reason |
| Backend unreachable | UI shows an explicit error and **zero** records; it never "optimistically" marks attendance |

## 7. Explicit non-goals for this document

No capacity model (single-institution scale), no RPO/RTO numbers until a real deployment exists,
no SLA. Those are recorded in [`hosting.md`](hosting.md) once a host is chosen.
