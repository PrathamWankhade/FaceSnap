# Biometric consent notice (template)

Status: **template** — an institution must have its legal/privacy office review and localise this
before collecting real student data. The version string below is the one the application enforces
(`CONSENT_VERSION`, default `2026-11`); bump it whenever the text or the data practice changes.

## What FaceSnap collects

- One enrollment photo, captured by the student (or by staff with the student present).
- A 512-dimensional ArcFace embedding derived from that photo.
- Attendance rows: date/time, method (live, doorway, upload, stream), match distance, liveness
  score, and the class session if one was selected.
- Account identity from the institution's Google identity (name, email, Firebase uid). No password
  is stored by FaceSnap.

## Why

To verify that the person marking attendance is the enrolled student, and to keep evidence for a
disputed attendance record. The photo is not used to train a model, sold, or shared with third
parties.

## Where it lives

- Photo: `FACE_IMAGE_DIR` on the server, outside the relational database.
- Embedding: the Qdrant vector index (derived; rebuildable from the photo).
- Attendance and consent record: the SQL database (system of record).

## Who can see it

- The student: their own profile, photo (`GET /api/students/me/face`), attendance and export.
- Staff (admin/operator): academic/attendance data and the enrollment state, **not** the photo.
- The photo is never returned in list or profile responses.

## Retention and withdrawal

- Attendance retention is opt-in: an operator runs `backend/scripts/purge_retention.py --days N`
  (dry run by default; applies with `--apply`) and the purge is audited.
- The student can delete their profile at any time (`DELETE /api/students/{id}`): this removes the
  photo, embedding and attendance history. Re-enrollment is possible afterwards.
- The consent version and timestamp are stored with the student row; after a notice update, rows
  with an older version can be queried for re-consent. The student scan shows a blocking
  `ConsentGate` modal for those rows and unlocks attendance only after `POST /api/consent/accept`
  records the current version (audited).

## What FaceSnap does not do

- No emotion recognition, no age/gender inference, no watchlist or surveillance analytics.
- No liveness certification: the check is best-effort and unevaluated against a spoof corpus.
- No biometric data in logs or metrics.

## Acknowledgement

The register page requires the student to accept this notice (`consent_version`) before the server
will enroll them. Enrollment without the current version is rejected with `422`.
