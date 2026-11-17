# Paper ↔ repository alignment

This page exists because the conference paper ("FaceSnap: Revolutionizing Student Attendance with
Advanced Facial Recognition", ICAIA 2025) claims capabilities that the repository did not implement.
The rule is simple: **the paper may only claim what the code does, and code may not hide behind the
paper.** Each row below records the claim, the truth, the evidence in this repo, and the wording the
paper should use.

Status: resolved for A1–A5 and B6–B10. Where a claim was removed, the removal is deliberate and
documented; where it was implemented, tests exist.

## A. Claims that had no code

| # | Paper claim | Resolution | Evidence |
|---|---|---|---|
| A1 | Emotion recognition as a "new capability" | **Removed.** Not implemented; no model, no endpoint, no dataset, no consent basis. Emotion inference on students would need its own privacy review. | Out of scope in [`system-design.md`](system-design.md); no `emotion` symbol in `backend/app/` |
| A2 | Low-light image processing improvement | **Implemented as conditional preprocessing**, not a trained enhancement model: if mean luminance < 90, CLAHE on LAB L + a capped gamma lift toward 115; bright frames pass through byte-identical. Applied to detection and embedding on every path. | `enhance_low_light()` in `backend/app/services/face_service.py`; `tests/test_preprocessing.py` (no-op when bright, lift when dark, capped gain) |
| A3 | "YOLO-based detection" | **False and removed.** Detection is InsightFace's detector. The unused `backend/yolov8n.pt` asset was deleted from the repository. | `git log -- backend/yolov8n.pt`; no `ultralytics`/`yolo` import; [`decisions/0006`](decisions/0006-pretrained-arcface.md) |
| A4 | ">95% accuracy in optimal conditions" | **No number claimed.** A reproducible harness now exists: FAR/FRR/EER/accuracy over labelled genuine/impostor pairs, with pair-file hash, model string and timestamp. A number is published only when the harness is run on a named, licensed dataset. | `backend/scripts/evaluate_recognition.py`; `app/services/evaluation.py`; `tests/test_evaluation.py`; [`evaluation.md`](evaluation.md) |
| A5 | "CNN" implying a custom-trained model | **Corrected.** Recognition is pretrained ArcFace (`InsightFace buffalo_s`, 512-d) used as a feature extractor; no training code exists. | [`decisions/0006`](decisions/0006-pretrained-arcface.md); `face_service._load_model()` |

## B. Claims that were oversold

| # | Paper claim | Truth | Correct wording |
|---|---|---|---|
| B6 | "One-shot attendance model" | Enrollment is one shot; attendance verification is a ~50-frame burst over ~5 s (rPPG + blink + motion). Calling both "one-shot" hides the actual liveness design. | "One-shot enrollment, multi-frame liveness-verified attendance." |
| B7 | "Scalability" | Single institution, single camera stream. Postgres and Redis are supported configuration, not a demonstrated multi-node deployment; no capacity benchmark has been run. | "Designed for single-institution scale; Postgres/Redis are supported for multi-worker hosts but are not load-tested here." |
| B8 | "Advanced analytics" | `/api/analytics/overview` returns counts, 7-day attendance, method and department breakdowns. That is operational reporting, not analytics. | "Operational attendance overview (counts and breakdowns)." |
| B9 | "Real-time processing" | The overlay runs per frame, but no latency SLO was measured or published. Per-route latency is now exported as a Prometheus histogram. | "Interactive per-frame overlay; latency is measured per route (`/api/metrics`) and no SLO is claimed until benchmarked." |
| B10 | "Automation" | Scans are started by staff. The loop then detects, matches and writes idempotently, but nothing schedules autonomous attendance decisions. | "Staff-triggered scan loop with automated detection, matching and idempotent writes. No unattended scheduling." |

## C. Repo strengths the paper should cite (not gaps)

These are concrete and tested; use them instead of unbacked accuracy claims.

- **Numbered NFRs** (`docs/system-design.md` §4): NFR-C1…C3, NFR-S1…S5, NFR-P1…P3, NFR-O1…O5,
  NFR-F1…F3, NFR-Q1…Q3. Cite them as the requirements baseline.
- **Database-enforced idempotency**: unique `(student_id, session_id)` plus a partial unique index
  on `(student_id, method, date(captured_at)) WHERE session_id IS NULL`; concurrent retries produce
  one row. Tests in `tests/test_registry_api.py`.
- **Server-side match only**: the browser cannot declare a match or write attendance (NFR-C1).
- **DB-authoritative roles**: Firebase proves identity; `users.role` decides authority (NFR-S1).
- **Audit + correlation**: audit rows for sensitive actions, `X-Request-Id` on every request, JSON
  logs in production (NFR-O2/O3).
- **Liveness as best-effort**: rPPG + blink + motion; explicitly not certified PAD. Honest
  limitation, real differentiator versus a single-image matcher.
- **Privacy posture**: no biometrics in SQL, owner-only photo fetch, self-service deletion,
  rebuildable derived index (NFR-P1/P2, NFR-C3).
- **Test suite**: 50+ backend tests including the permission/IDOR matrix, liveness sampling,
  production guards, metrics and evaluation math; Playwright covers the unauthenticated browser
  surface; CI runs lint, type-check, build, tests, ruff, dependency audits and secret scanning.

## D. Paper rewrite checklist

1. Replace ">95% accuracy" with the result of `scripts/evaluate_recognition.py` on a named dataset,
   or state "no accuracy claim; evaluation harness provided".
2. Delete "emotion recognition" and "low-light model". If low-light is mentioned, describe it
   exactly as conditional CLAHE + capped gamma, and cite the unit tests — not a learned model.
3. Delete "YOLO". Say "InsightFace detector + pretrained ArcFace (`buffalo_s`) embeddings".
4. Replace "one-shot attendance" with "one-shot enrollment + multi-frame verified attendance".
5. Scope "scalability" and "automation" per B7/B10; rename "advanced analytics" per B8.
6. Add a methodology section that cites this repository's NFRs, idempotency constraints, liveness
   design and privacy model. The docs are written to be citable.
7. Add a limitations paragraph: best-effort liveness, single camera stream, opt-in attendance
   retention with no automatic biometric expiry, no multi-node benchmark, no certified PAD.

## E. What is still not true (do not write these)

- "Certified anti-spoofing" / "PAD-certified" — liveness is best-effort and unevaluated against a
  spoof corpus.
- "Production-ready" / "deployed at scale" — local SQLite + local Qdrant is the shipped default; no
  staging or production host exists yet.
- "Multi-tenant" / "SaaS" — single institution by design ([`decisions/0002`](decisions/0002-multi-tenancy.md)).
- "Real-time CCTV fleet" — `/cctv` is one stream ([`system-design.md`](system-design.md) §3).
- Any specific accuracy, FAR or latency figure that this repository has not produced.
