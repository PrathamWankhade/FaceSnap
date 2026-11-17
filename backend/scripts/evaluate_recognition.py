#!/usr/bin/env python
"""Reproducible 1:1 recognition evaluation (FAR/FRR/EER/accuracy).

No dataset and no accuracy number ships with this repository: biometric data is
not committed, and an unmeasured benchmark must never be quoted. This script is
the harness that produces a number *when a dataset is available*.

Pair formats
------------
``pairs.csv`` (recommended, dataset-agnostic):

    path_a,path_b,label
    alice/1.jpg,alice/2.jpg,genuine
    alice/1.jpg,bob/1.jpg,impostor

Relative paths resolve against ``--dataset``.

``pairs.txt`` (LFW layout):

    Alice 1 2            # genuine pair: dataset/Alice/Alice_0001.jpg vs _0002.jpg
    Alice 1 Bob 1        # impostor pair

Usage
-----
    cd backend
    python scripts/evaluate_recognition.py --dataset /data/lfw --pairs /data/lfw/pairs.txt
    python scripts/evaluate_recognition.py --dataset /data/campus --pairs pairs.csv \
        --out reports/recognition.json --min-accuracy 0.90

Reported protocol: model ``InsightFace buffalo_s`` (ArcFace, 512-d, L2-normalised),
cosine distance, decision ``distance <= threshold``. The threshold sweep reports
FAR/FRR/accuracy at every observed distance, plus the equal-error-rate point and
the best-accuracy point. Compare the best-accuracy threshold with the deployed
``ARCFACE_THRESHOLD`` (0.35) before changing it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ARCFACE_THRESHOLD  # noqa: E402
from app.services.evaluation import evaluate  # noqa: E402
from app.services.face_service import face_service  # noqa: E402


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {}
    ordered = sorted(values)

    def pick(p: float) -> float:
        index = max(0, min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1)))))
        return round(ordered[index], 3)

    return {
        "count": len(ordered),
        "p50_ms": pick(50),
        "p95_ms": pick(95),
        "p99_ms": pick(99),
        "mean_ms": round(statistics.fmean(ordered), 3),
    }


def _parse_label(raw: str) -> int:
    value = raw.strip().lower()
    if value in {"1", "genuine", "same", "true"}:
        return 1
    if value in {"0", "impostor", "different", "false"}:
        return 0
    raise ValueError(f"unknown pair label: {raw!r}")


def load_csv_pairs(path: Path, dataset: Path) -> list[tuple[Path, Path, int]]:
    pairs: list[tuple[Path, Path, int]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) not in (3, 4):
            raise ValueError(f"{path}:{line_number}: expected 'path_a,path_b,label[,group]'")
        if line_number == 1 and parts[0].lower() in {"path_a", "image_a"}:
            continue  # header row
        a, b, label = parts[0], parts[1], parts[2]
        group = parts[3] if len(parts) == 4 else None
        pairs.append((dataset / a, dataset / b, _parse_label(label), group))
    return pairs


def load_lfw_pairs(path: Path, dataset: Path) -> list[tuple[Path, Path, int]]:
    pairs: list[tuple[Path, Path, int]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        try:
            if len(parts) == 3:
                name, first, second = parts
                pairs.append(
                    (
                        dataset / name / f"{name}_{int(first):04d}.jpg",
                        dataset / name / f"{name}_{int(second):04d}.jpg",
                        1,
                        None,
                    )
                )
            elif len(parts) == 4:
                name_a, first, name_b, second = parts
                pairs.append(
                    (
                        dataset / name_a / f"{name_a}_{int(first):04d}.jpg",
                        dataset / name_b / f"{name_b}_{int(second):04d}.jpg",
                        0,
                        None,
                    )
                )
            else:
                raise ValueError("expected 3 or 4 columns")
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return pairs


def embed(path: Path, cache: dict[Path, list[float] | None], timings: list[float]):
    key = path.resolve()
    if key in cache:
        return cache[key]
    try:
        raw = path.read_bytes()
    except OSError:
        cache[key] = None
        return None
    started = time.perf_counter()
    encoding = face_service.get_face_encoding(raw)
    timings.append((time.perf_counter() - started) * 1000)
    cache[key] = encoding
    return encoding


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, type=Path, help="dataset root directory")
    parser.add_argument("--pairs", type=Path, help="pairs.csv or LFW pairs.txt (default: <dataset>/pairs.csv)")
    parser.add_argument("--out", type=Path, help="write the JSON report here")
    parser.add_argument("--limit", type=int, default=0, help="evaluate at most N pairs (0 = all)")
    parser.add_argument("--min-accuracy", type=float, default=None, help="exit 3 if best accuracy is below this")
    parser.add_argument("--max-eer", type=float, default=None, help="exit 3 if EER is above this")
    parser.add_argument("--breakdown-by", type=str, default=None, help="name of the demographic column in pairs.csv (4th field); reports per-group metrics")
    args = parser.parse_args(argv)

    if not face_service.is_ready:
        print("Face model is not loaded; cannot evaluate. Check the InsightFace model pack.", file=sys.stderr)
        return 2

    dataset: Path = args.dataset
    pairs_path: Path = args.pairs or (dataset / "pairs.csv")
    if not pairs_path.exists():
        print(f"No pairs file at {pairs_path}. See the script docstring for the required format.", file=sys.stderr)
        return 2

    raw_pairs = (
        load_lfw_pairs(pairs_path, dataset)
        if pairs_path.suffix.lower() == ".txt"
        else load_csv_pairs(pairs_path, dataset)
    )
    if args.limit:
        raw_pairs = raw_pairs[: args.limit]
    if not raw_pairs:
        print(f"{pairs_path} contains no pairs.", file=sys.stderr)
        return 2

    cache: dict[Path, list[float] | None] = {}
    timings: list[float] = []
    distances: list[float] = []
    labels: list[int] = []
    groups: list[str | None] = []
    skipped = 0
    started = time.perf_counter()

    for path_a, path_b, label, group in raw_pairs:
        encoding_a = embed(path_a, cache, timings)
        encoding_b = embed(path_b, cache, timings)
        if encoding_a is None or encoding_b is None:
            skipped += 1
            continue
        match, _score, distance = face_service.verify_faces(encoding_a, encoding_b)
        del match  # the sweep re-decides at every threshold
        distances.append(distance)
        labels.append(label)
        groups.append(group)

    if not distances:
        print("No usable pairs (every image failed face detection).", file=sys.stderr)
        return 2

    report = evaluate(distances, labels)
    # Optional per-group breakdown (Phase 6.4): pairs.csv may carry a 4th column.
    if any(g is not None for g in groups):
        breakdown = {}
        for group_name in sorted({g for g in groups if g is not None}):
            idx = [i for i, g in enumerate(groups) if g == group_name]
            if not idx:
                continue
            sub_distances = [distances[i] for i in idx]
            sub_labels = [labels[i] for i in idx]
            try:
                breakdown[group_name] = evaluate(sub_distances, sub_labels)
            except ValueError:
                breakdown[group_name] = {"error": "insufficient pairs"}
        report["breakdown"] = breakdown
    report.update(
        {
            "dataset": str(dataset),
            "pairs_file": str(pairs_path),
            "pairs_sha256": hashlib.sha256(pairs_path.read_bytes()).hexdigest(),
            "model": "InsightFace buffalo_s (ArcFace, 512-d, L2-normalised)",
            "metric": "cosine distance, match if distance <= threshold",
            "deployed_threshold": ARCFACE_THRESHOLD,
            "pairs_evaluated": len(distances),
            "pairs_skipped": skipped,
            "embed_latency": _percentiles(timings),
            "wall_seconds": round(time.perf_counter() - started, 2),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )

    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"\nReport written to {args.out}", file=sys.stderr)

    failed = False
    if args.min_accuracy is not None and report["best_accuracy"] < args.min_accuracy:
        print(
            f"Gate failed: best accuracy {report['best_accuracy']:.4f} < {args.min_accuracy:.4f}",
            file=sys.stderr,
        )
        failed = True
    if args.max_eer is not None and report["eer"] > args.max_eer:
        print(f"Gate failed: EER {report['eer']:.4f} > {args.max_eer:.4f}", file=sys.stderr)
        failed = True
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
