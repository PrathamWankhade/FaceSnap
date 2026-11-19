# ADR 0007 — Model swap and re-enrollment procedure

Status: Accepted (procedure documented; no swap performed yet).

## Context

FaceSnap records which recognition model produced each enrolled embedding
(`students.model_version`, set at enroll/backfill). A model swap therefore
needs two things: (1) a way to tell which students are on the old model,
and (2) a re-enrollment campaign. The infrastructure for (1) exists
(`/api/admin/model-info`, `/api/admin/model-version/retag`). The corpus,
licence and evaluation report for a new model do not.

## Decision

- A model change is never applied silently. It requires an ADR, a named
  model, a licence, and an evaluation report (FAR/FRR/EER on a named
  dataset) before any re-enrollment.
- Procedure:
  1. Drop the new model files into `backend/app/.insightface/models/<name>/`
     and point `INSIGHTFACE_MODEL` (or the config) at it; bump `MODEL_VERSION`.
  2. Restart the backend. `/api/admin/model-info` now reports
     `needs_reenrollment = students_total`.
  3. Run a re-enrollment campaign (staff re-captures faces; `/api/students/enroll`
     overwrites the embedding and stamps the new `model_version`).
  4. Once everyone is on the new version, call
     `POST /api/admin/model-version/retag` to normalise any stragglers.
  5. Keep the old model files for one release cycle for rollback.
- Rollback = revert `MODEL_VERSION`, restart, and re-tag. Embeddings from
  the new model are not reusable by the old one, so a rollback implies
  re-enrollment again. This is documented, not hidden.

## Consequences

- No automatic model download or hot-swap. A human must procure, evaluate
  and approve a model before it ships.
- `model-info` + `retag` make the campaign observable and auditable.