# Permissions

Authority: `backend/app/auth.py`. Enforced **server-side on every route** — the frontend only hides
controls the user cannot use (defence in depth, not the boundary).

Roles live in `users.role` (`admin` | `operator` | `student`). Token claims are never consulted.

| Role | Granted by | Typical holder |
|------|-----------|----------------|
| `admin` | `ADMIN_EMAILS` on first login, or `PATCH /api/users/{uid}/role` | College IT / project owner |
| `operator` | promoted by an admin | Teachers, doorway operators |
| `student` | default for every new identity | Everyone else |

**Staff = `admin` ∪ `operator`.** `STAFF_ROLES = ("admin", "operator")`.

## Route matrix

Legend — **Auth**: `—` public · `User` any authenticated identity · `Staff` admin/operator ·
`Admin` · `Owner` the caller's own student profile (staff also allowed) ·
`Staff/Key` staff user **or** `X-Service-Key` matching `PI_SERVICE_KEY`.

| Method | Path | Auth | Data scope | Notes |
|--------|------|------|-----------|-------|
| GET | `/` | — | engine + counts | no PII beyond aggregate counts |
| GET | `/api/health` | — | component readiness | never touches the model (NFR-O1) |
| GET | `/api/health/live` | — | process liveness | for uptime probes |
| GET | `/api/me` | User | caller | role + own student profile |
| PATCH | `/api/users/{uid}/role` | Admin | target user | audited; admin cannot demote themselves (see below) |
| POST | `/api/students/enroll` | User | self; **Staff** may specify another `user_uid` | exactly one face required; audited |
| GET | `/api/students` | User | **Staff:** all · **Student:** self only | filtered by `department` for staff |
| GET | `/api/students/me` | User | self | `404` if the caller has no student row |
| GET | `/api/students/me/face` | User | self | owner-only biometric fetch (NFR-P1) |
| DELETE | `/api/students/{student_id}` | Owner/Staff | self or any for staff | deletes photo, embedding, attendance; audited |
| POST | `/api/attendance` | User | self; **Staff** may pass `student_uid` | idempotent; DB-enforced uniqueness |
| GET | `/api/attendance` | User | **Staff:** all · **Student:** own | filters: `student_uid`, `method`, `session_id`, `from`, `to`, `limit` |
| GET | `/api/attendance/summary` | User | same isolation as above | per-day totals over N days |
| GET | `/api/analytics/overview` | Staff | institution-wide | `403` for students |
| POST | `/api/sessions` | Staff | creates; `teacher_id` = caller | audited |
| GET | `/api/sessions` | User | institution-wide (no PII beyond room/title) | students need this to pick a session |
| POST | `/api/leave` | User | own student row only | `session_id` must exist |
| GET | `/api/leave` | User | **Staff:** all · **Student:** own | |
| POST | `/api/admin/backfill-embeddings` | Admin | whole index | audited rebuild of Qdrant from SQL |
| POST | `/api/verify` | Staff | arbitrary two images | deliberately **not** student-callable: it would be a general face-comparison oracle |
| POST | `/api/verify_liveness` | User | caller's own enrollment template | frames + measured `frame_interval_ms`; rate-limited |
| POST | `/api/sync` | Staff | bulk import | legacy bulk path; prefer enroll/backfill |
| POST | `/api/detect_webcam` | Staff | frame → detections + identities | rate-limited |
| GET | `/api/pi/health` | Staff/Key | camera/engine state | |
| GET | `/api/pi/stream` | Staff/Key | MJPEG | browsers cannot attach a bearer header to `<img>`; use a proxy or the capture/detect endpoints |
| GET | `/api/pi/capture` | Staff/Key | still frame | |
| GET | `/api/pi/detect` | Staff/Key | faces + `match` or `null` | unknown faces return `null`, never a guess |

## Rules that must not regress

1. **No unguarded route.** A new route without an explicit `Depends(...)` (even a bare
   `get_current_user_row`) is a bug. Add the row to this file in the same change.
2. **Student lists are self-scoped in SQL**, not by dropping rows after the query. The pattern is
   `if user.role not in STAFF_ROLES: stmt = stmt.where(Student.user_id == user.id)`.
3. **Cross-object checks are per-object.** Enrollment, attendance and deletion compare
   `target != caller` before allowing staff-only operations.
4. **Biometric reads are owner-only.** `/api/students/me/face` has no "by id" counterpart.
5. **Camera/matching endpoints are staff or service key.** `require_camera_caller` compares the
   key with `hmac.compare_digest`.
6. **Admin privilege changes are audited** (`audit_log` rows via `_audit`).

## Known, deliberate trade-offs

- **`/api/verify_liveness` accepts client-supplied frames.** It is authenticated and rate-limited,
  and the reference image is the caller's *own* enrollment photo (server-resolved), so it does not
  become a comparison oracle. It still costs CPU — hence `RATE_LIMIT_PER_MINUTE`.
- **Students can list all class sessions.** Session titles/rooms are not personal data and the
  student flow needs them.
- **Development bypass (`REQUIRE_AUTH=false`) makes everyone an admin.** It is refused in
  production by `_validate_runtime()` and at request time by `get_current_user()`.

## Test coverage

`backend/tests/test_permissions.py` asserts, for every row above: `401` with no token, `403` for
the wrong role, and **no cross-user read** for student-scoped routes (NFR-S1, NFR-S3).
`docs/testing.md` explains how to extend it.
