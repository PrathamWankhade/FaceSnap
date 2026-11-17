# 0006 — Use pretrained ArcFace (InsightFace `buffalo_s`); do not train a CNN

- Status: accepted
- Date: 2026-11-16
- Supersedes: nothing

## Context

The companion paper describes the recognition step as a "deep learning network from CNN, YOLO and
ML" and implies a custom-trained model. The repository does neither: it loads InsightFace's
`buffalo_s` pack (RetinaFace-family detector + ArcFace 512-d embedding model) and performs cosine
matching. There is no training code, no dataset pipeline and no fine-tuning in this project.

The unused `backend/yolov8n.pt` asset reinforced the wrong impression: it was never imported, and
detection has always come from InsightFace. It has been deleted.

## Decision

1. Recognition is **pretrained ArcFace (`buffalo_s`) used as a feature extractor**, with a fixed
   cosine-distance threshold (`ARCFACE_THRESHOLD`, default `0.35`). No training happens in this
   repository and none is planned for v1.
2. Face detection is InsightFace's detector. No YOLO model is used, and no YOLO asset ships.
3. Any accuracy claim must come from `backend/scripts/evaluate_recognition.py` against a named,
   licensed dataset, with the protocol and pair file hash recorded in `docs/evaluation.md`. Until
   that run exists, the repo claims **no accuracy number**.
4. Language in README, docs and the paper is "pretrained ArcFace (InsightFace `buffalo_s`)" — not
   "custom CNN".

## Consequences

- The system inherits ArcFace's strengths on frontal, well-lit faces and its weaknesses on extreme
  pose, occlusion and low resolution. Those are documented limitations, not hidden.
- No training pipeline means no dataset licensing, GPU budget or model-provenance problem.
- Swapping models (e.g. `buffalo_l`) is a one-line change plus a full re-enrollment/backfill, since
  embeddings from different models are not comparable. That migration would need its own ADR.
- A future fine-tuned model is allowed, but it must arrive with a training corpus, a licence, an
  evaluation report and a re-embedding plan.
