# Architecture

FaceSnap is two applications that talk over authenticated HTTPS — a presentation layer and a recognition authority. The core rule: **the browser never declares a match and never writes trusted attendance.**

```
+------------------+   Firebase ID token   +----------------------+
|  Next.js 15      |---------------------->|  FastAPI             |
|  + Firebase Auth |   (or X-Service-Key   |  /api/verify*        |
|    (identity)    |    for cameras)       |  /api/detect_webcam  |
|  UI + camera     |                       |  /api/students/*     |
|  controls        |                       |  /api/attendance     |
+---------+--------+                       |  /api/sessions       |
          |                                |  /api/pi/*           |
          | REST (JSON)                    +----+--------+--------+
          +---------------------------------->|        |
                                               |        |
                                    +----------v--+  +--v-----------------+
                                    | SQLAlchemy  |  | Qdrant (derived)   |
                                    | system of   |  | 512-dim embeddings |
                                    | record      |  +--------------------+
                                    | SQLite/PG   |
                                    +------+------+
                                           |
                                    +------v-----------+
                                    | Face image store |
                                    | ./data/faces     |
                                    +------------------+
```

Firebase is now **identity only**. Users, roles, students, sessions, attendance, leave and audit live in the relational database, which is the single source of truth. Qdrant and the image store are derived/supporting stores.

## Layers and responsibilities

| Layer | Owns | Must never |
|-------|------|------------|
| Next.js frontend | Portals, dashboards, camera controls, review UI, theme | Declare a match or write attendance directly |
| FastAPI auth (`app/auth.py`) | ID-token verification, DB-backed role resolution, service-key gate for cameras | Trust caller-supplied UID or token-claim role |
| Registry (`routes/registry.py`) | Enrollment, students, attendance, sessions, leave, analytics | Accept attendance without a student row |
| Recognition (`face_service`) | Image guardrails (8 MB / 4096 px), ArcFace embeddings, cosine-distance matching | Treat detection as identity |
| Liveness (`liveness_service`) | rPPG pulse + blink + motion scoring over 5–60 frames | Pass a static/repeated frame set as "live" |
| Database (`db.py`) | Relational schema, unique attendance constraint, audit trail | Store biometric originals |
| Vector cache (`vector_service`) | Qdrant embeddings, rebuildable from SQL via `/api/admin/backfill-embeddings` | Act as the source of truth for enrollment |
| Image store (`image_store`) | Enrollment photos keyed by student id | Expose photos to anyone but the owner |
| Camera (`camera`) | Explicit lifecycle (`start`/`read`/`stop`), `health()` with `last_error` | Confuse stream visibility with recognition health |

## Recognition pipeline

1. **Capture** — webcam frame (base64) or Pi camera frame.
2. **Guardrails** — size/dimension/decode checks; enrollment requires exactly one detected face.
3. **Detect + embed** — InsightFace `buffalo_s` via ONNX Runtime (CPU or CUDA), embeddings L2-normalized.
4. **Match** — cosine distance against Qdrant (`1 - cosine_similarity`), threshold `ARCFACE_THRESHOLD = 0.35`. Float noise is clamped to `0.0`.
5. **Liveness** (verification flow) — 30 frames analyzed for pulse, blink, motion. A strong pulse (`≥ 0.6`) passes on its own; otherwise the combined score must clear `0.5`. Frames with no temporal colour variation are rejected outright.
6. **Record** — `POST /api/attendance` writes an idempotent row (unique per student+session, else per day/method). The UI shows *verified* and *recorded* as separate states.

## Data model

Relational (SQLAlchemy, `backend/app/db.py`):

- `users` — provider subject (`id`), email, display name, authoritative `role` (`admin` | `operator` | `student`).
- `students` — one row per user (`user_id` unique), roll number (unique), department/year/semester, `face_image_key`.
- `departments`, `courses`, `class_sessions` — academic structure; attendance can be scoped to a session.
- `attendance` — student, optional session, timestamp, method, liveness score, distance. Unique `(student_id, session_id)`; indexed history.
- `cameras`, `leave_requests`, `audit_log`.

Supporting stores:

- `FACE_IMAGE_DIR` (`./data/faces`) — enrollment JPEGs; only the key is in SQL.
- Qdrant `students` collection — 512-dim cosine vectors with `{ uid, name, roll_no }`; point IDs derive deterministically from the user id so re-enrollment updates in place.

## Key files

- `backend/app/db.py` — relational schema, engine/session, UTC helpers
- `backend/app/routes/registry.py` — students, attendance, sessions, leave, analytics
- `backend/app/auth.py` — token verification, `get_current_user_row`, `require_roles`, `require_camera_caller`
- `backend/app/services/face_service.py` — embeddings + `verify_faces`
- `backend/app/services/liveness_service.py` — rPPG/blink/motion with static-frame guard
- `backend/app/services/image_store.py` — local object store
- `backend/tests/` — matching math, registry API, liveness regression
- `frontend/lib/api.ts` — authenticated backend client
- `frontend/lib/attendance.ts` — `markAttendance()` + `authHeaders()`
