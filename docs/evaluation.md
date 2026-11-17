# Recognition evaluation

Status: harness implemented, **no benchmark has been run against a named dataset in this
repository**, so **no accuracy number is claimed**.

A paper or README that says ">95% accuracy" without a dataset, protocol and pair file is not making
a measurable claim. This page exists so the number can be produced and audited, not asserted.

## What is measured

1:1 verification on image pairs. Each pair is labelled **genuine** (same person) or **impostor**
(different people). The model produces an ArcFace embedding per image and a cosine distance per
pair; a pair is accepted when `distance <= threshold`.

Reported per run:

| Metric | Definition |
|---|---|
| FAR | false accepts ÷ impostor pairs |
| FRR | false rejects ÷ genuine pairs |
| EER | point where FAR = FRR (linearly interpolated between observed thresholds) |
| best accuracy | max over thresholds of `(TP + TN) / pairs`, with its threshold, FAR and FRR |
| embed latency | p50/p95/p99 of `get_face_encoding` per unique image |

Accuracy alone is misleading for a biometric system: a high accuracy at a permissive threshold can
hide an unacceptable FAR. Always report the FAR/FRR pair at the operating threshold.

## Running it

```bash
cd backend
python scripts/evaluate_recognition.py \
  --dataset /data/lfw \
  --pairs /data/lfw/pairs.txt \
  --out reports/lfw-buffalo_s.json
```

Pair formats:

- `pairs.csv` (dataset-agnostic, recommended): `path_a,path_b,label` where label is
  `genuine`/`impostor` or `1`/`0`. Paths are relative to `--dataset`.
- LFW `pairs.txt` layout: `Name idx1 idx2` (genuine) and `NameA idx1 NameB idx2` (impostor).

Optional gates for a CI job that has the dataset mounted:

```bash
python scripts/evaluate_recognition.py --dataset /data/eval --pairs pairs.csv \
  --min-accuracy 0.90 --max-eer 0.08     # exit 3 on failure
```

The JSON report records the dataset path, the pairs file SHA-256, the model string, the deployed
threshold (`ARCFACE_THRESHOLD`), the evaluated/skipped pair counts and the timestamp. That is what
makes a published number reproducible.

## Dataset handling (non-negotiable)

- **Never commit evaluation images.** LFW/CFP-FP and any campus set are biometric data; they stay
  outside the repository and out of CI caches. `data/`, `*.jpg` datasets and `reports/` are ignored.
- Record the dataset name, version/licence and the pair-file hash in the report; a number without
  provenance is not evidence.
- A campus dataset needs consent, a retention policy and an ethics/IRB decision before collection.

## Interpreting a result

- The deployed threshold is `ARCFACE_THRESHOLD=0.35`. If the best-accuracy threshold is far from
  0.35, either the threshold or the model is wrong for this population; do not simply move the
  threshold to maximise accuracy — choose it from the acceptable FAR for an attendance use case.
- Cross-dataset numbers do not transfer. LFW is easy, frontal and web-quality; a doorway camera at
  1080p with motion blur is a different distribution. A campus pilot set is the relevant one.
- Low-light preprocessing (`enhance_low_light`) is applied before embedding. Evaluate with and
  without it on a dark subset before claiming it helps; the unit tests only prove it is conditional
  and bounded, not that it improves recognition.

## CI position

The offline suite tests the **metric implementation** (`tests/test_evaluation.py`), not model
accuracy. CI has no dataset and no model download, so it cannot produce a recognition number. A
benchmark job would need a licensed dataset mounted as a secret/artifact and is intentionally not
wired yet.
