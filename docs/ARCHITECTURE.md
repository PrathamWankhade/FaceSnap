# Architecture

FaceSnap is two applications that talk over authenticated HTTPS — a presentation layer and a recognition authority. The core rule: **the browser never declares a match and never writes trusted attendance.**

```
+------------------+   Firebase ID token   +---------------------+
|  Next.js 15      |---------------------->|  FastAPI            |
|  + Firebase Auth |   (or X-Service-Key   |  /api/verify*       |
|  Firestore/      |    for cameras)       |  /api/detect_webcam |
|  Storage client  |                       |  /api/sync (staff)  |
|  camera controls |                       |  /api/pi/* (camera) |
|  review UI       |                       +----------+----------+
+---------+--------+                                  |
          | Firestore (client SDK)          +---------v---------+
          +-------------------------------->| Firestore (Admin) |
                                            | Qdrant embeddings |
                                            | Storage images    |
                                            +-------------------+
```

## Layers and responsibilities

| Layer | Owns | Must never |
|-------|------|------------|
| Next.js frontend | Portals, dashboards, camera controls, review UI, theme | Declare a match or write trusted attendance directly |
| FastAPI auth (`app/auth.py`) | ID-token verification, role gates, service-key gate for cameras | Trust caller-supplied UID or role |
| Recognition (`face_service`) | Image guardrails (8 MB / 4096 px), ArcFace embeddings, cosine-distance matching | Treat detection as identity; return calibrated "confidence" |
| Liveness (`liveness_service`) | rPPG pulse + blink + motion scoring over 5–60 frames | Pass a single still image as "live" |
| Attendance (client builder + rules) | Canonical schema, one write per session per student (client dedupe set + server rules) | Create records on API exceptions or uncertain matches |
| Vector cache (`vector_service`) | Qdrant embeddings, rebuildable from Firestore via `/api/sync` | Act as the source of truth for enrollment |
| Camera (`camera`) | Explicit lifecycle (`start`/`read`/`stop`), `health()` with `last_error` | Confuse stream visibility with recognition health |

## Recognition pipeline

1. **Capture** — webcam frame (base64) or Pi camera frame.
2. **Guardrails** — size/dimension/decode checks; multi-face enrollment captures are rejected.
3. **Detect + embed** — InsightFace `buffalo_s` via ONNX Runtime (CPU or CUDA), embeddings L2-normalized.
4. **Match** — cosine distance against Qdrant (`1 - cosine_similarity`), threshold `ARCFACE_THRESHOLD = 0.35`. Sub-`1e-9` float noise is clamped to `0.0`.
5. **Liveness** (verification flow) — 30 frames analyzed for pulse, blink, motion; combined score must clear `0.5`.
6. **Record** — canonical `AttendanceRecord` with method + optional liveness score; UI shows *verified* and *recorded* as two separate states.

## Data model

- `users/{uid}` — `{ uid, email, displayName?, role: 'admin' | 'student', createdAt }`. New sign-ins default to `student`; promotion is a privileged write, never self-service.
- `students/{id}` — profile + academic fields + `faceImageBase64` capture. Owner-writable, broadly readable by signed-in users (see Security doc for the tightening plan).
- `attendance/{id}` — canonical schema; create-only for the record owner; immutable afterwards; admin-deletable.
- Storage `faces/{uid}/{timestamp}.jpg` — originals; deleted recursively on request.
- Qdrant `students` collection — 512-dim cosine vectors with `{ uid, name, roll_no }` payloads; rebuilt from Firestore, never authoritative.

## Key files

- `backend/app/main.py` — app wiring, `/api/health`
- `backend/app/auth.py` — token verification, `require_role`, `require_camera_caller`
- `backend/app/services/face_service.py` — embeddings + `verify_faces`
- `backend/tests/test_face_service.py` — matching-math contract (list vs array equivalence, zero-vector/shape rejection)
- `frontend/lib/attendance.ts` — canonical record builder + `authHeaders()`
- `frontend/firestore.rules` — client security boundary
