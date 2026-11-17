"""Threshold sweep for 1:1 face recognition evaluation.

A "pair" is two images, labelled genuine (same person) or impostor (different
people). Distances are cosine distances from ArcFace embeddings; a pair is
predicted genuine when ``distance <= threshold``.

Everything here is pure math on numbers — no images, no model — so the metric
implementation is unit-testable offline and the evaluation script can be swapped
for any dataset without touching this module.
"""
from __future__ import annotations

from typing import Iterable, Sequence


def _validate(distances: Sequence[float], labels: Sequence[int]) -> None:
    if len(distances) != len(labels):
        raise ValueError("distances and labels must have the same length")
    if not distances:
        raise ValueError("at least one pair is required")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must be 0 (impostor) or 1 (genuine)")
    positives = sum(labels)
    if positives == 0:
        raise ValueError("no genuine pairs: FAR/FRR cannot be computed")
    if positives == len(labels):
        raise ValueError("no impostor pairs: FAR cannot be computed")


def confusion(distances: Sequence[float], labels: Sequence[int], threshold: float) -> dict:
    """Confusion counts at one operating threshold."""
    _validate(distances, labels)
    tp = fp = tn = fn = 0
    for distance, label in zip(distances, labels):
        predicted = distance <= threshold
        if label == 1:
            if predicted:
                tp += 1
            else:
                fn += 1
        else:
            if predicted:
                fp += 1
            else:
                tn += 1
    total = tp + fp + tn + fn
    far = fp / (fp + tn) if (fp + tn) else 0.0
    frr = fn / (fn + tp) if (fn + tp) else 0.0
    return {
        "threshold": float(threshold),
        "true_accept": tp,
        "false_accept": fp,
        "true_reject": tn,
        "false_reject": fn,
        "far": far,
        "frr": frr,
        "accuracy": (tp + tn) / total,
    }


def _candidate_thresholds(distances: Iterable[float]) -> list[float]:
    """Every distinct observed distance, plus just above the maximum.

    Matching is ``<=``, so each distinct distance is the only place a decision
    changes; the point above the maximum rejects everything.
    """
    unique = sorted({float(d) for d in distances})
    upper = unique[-1] + 1e-6
    return unique + [upper]


def equal_error_rate(
    distances: Sequence[float], labels: Sequence[int]
) -> tuple[float, float]:
    """Return ``(eer, threshold)`` interpolated where FAR and FRR cross."""
    _validate(distances, labels)
    previous: tuple[float, float, float, float] | None = None
    best: tuple[float, float, float, float] | None = None

    for threshold in _candidate_thresholds(distances):
        row = confusion(distances, labels, threshold)
        gap = row["far"] - row["frr"]
        if best is None or abs(gap) < abs(best[0]):
            best = (gap, row["far"], row["frr"], threshold)

        if previous is not None:
            prev_gap, prev_far, prev_frr, prev_threshold = previous
            if (prev_gap <= 0 <= gap) or (gap <= 0 <= prev_gap):
                if gap == prev_gap:
                    eer = (row["far"] + row["frr"]) / 2
                    crossing = threshold
                else:
                    ratio = abs(prev_gap) / (abs(prev_gap) + abs(gap))
                    eer = prev_frr + ratio * (row["frr"] - prev_frr)
                    crossing = prev_threshold + ratio * (threshold - prev_threshold)
                return float(max(0.0, min(1.0, eer))), float(crossing)
        previous = (gap, row["far"], row["frr"], threshold)

    # No sign change (possible with coarse data): closest achievable point.
    if best is None:  # pragma: no cover - _validate guarantees observations
        raise ValueError("no thresholds evaluated")
    return float((best[1] + best[2]) / 2), float(best[3])


def evaluate(
    distances: Sequence[float],
    labels: Sequence[int],
    thresholds: Iterable[float] | None = None,
) -> dict:
    """Full report: EER, best-accuracy operating point, and a threshold table."""
    _validate(distances, labels)
    eer, eer_threshold = equal_error_rate(distances, labels)

    candidates = list(thresholds) if thresholds is not None else _candidate_thresholds(distances)
    rows = [confusion(distances, labels, threshold) for threshold in candidates]
    best = max(rows, key=lambda row: (row["accuracy"], -row["false_accept"]))

    return {
        "pairs": len(labels),
        "genuine_pairs": int(sum(labels)),
        "impostor_pairs": int(len(labels) - sum(labels)),
        "eer": round(eer, 6),
        "eer_threshold": round(eer_threshold, 6),
        "best_accuracy": round(best["accuracy"], 6),
        "best_threshold": round(best["threshold"], 6),
        "best_far": round(best["far"], 6),
        "best_frr": round(best["frr"], 6),
        "thresholds": [
            {
                "threshold": round(row["threshold"], 6),
                "far": round(row["far"], 6),
                "frr": round(row["frr"], 6),
                "accuracy": round(row["accuracy"], 6),
            }
            for row in rows
        ],
    }
