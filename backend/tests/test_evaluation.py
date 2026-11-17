"""Recognition-evaluation math: confusion counts, threshold sweep, EER."""
import pytest

from app.services.evaluation import confusion, equal_error_rate, evaluate


def test_confusion_counts_and_rates():
    row = confusion([0.1, 0.6, 0.4, 0.9], [1, 1, 0, 0], threshold=0.5)
    assert row["true_accept"] == 1
    assert row["false_reject"] == 1
    assert row["false_accept"] == 1
    assert row["true_reject"] == 1
    assert row["far"] == 0.5
    assert row["frr"] == 0.5
    assert row["accuracy"] == 0.5


def test_perfect_separation_has_zero_eer():
    distances = [0.1, 0.2, 0.3, 0.5, 0.6, 0.9]
    labels = [1, 1, 1, 0, 0, 0]
    eer, threshold = equal_error_rate(distances, labels)
    assert eer == 0.0
    assert 0.3 <= threshold <= 0.5


def test_overlap_reports_eer_and_best_accuracy():
    distances = [0.1, 0.6, 0.4, 0.9]
    labels = [1, 1, 0, 0]
    eer, _threshold = equal_error_rate(distances, labels)
    assert eer == pytest.approx(0.5, abs=1e-9)

    report = evaluate(distances, labels)
    assert report["pairs"] == 4
    assert report["genuine_pairs"] == 2
    assert report["impostor_pairs"] == 2
    assert report["best_accuracy"] == pytest.approx(0.75)
    # Several thresholds tie at 0.75; the sweep keeps the first (lowest) one.
    assert report["best_threshold"] == pytest.approx(0.1)


def test_far_is_monotonic_and_frr_is_anti_monotonic():
    distances = [0.05, 0.2, 0.35, 0.5, 0.8]
    labels = [1, 1, 0, 0, 0]
    report = evaluate(distances, labels)
    thresholds = report["thresholds"]
    fars = [row["far"] for row in thresholds]
    frrs = [row["frr"] for row in thresholds]
    assert fars == sorted(fars)
    assert frrs == sorted(frrs, reverse=True)


def test_threshold_table_can_be_supplied():
    report = evaluate([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0], thresholds=[0.35, 0.5])
    assert [row["threshold"] for row in report["thresholds"]] == [0.35, 0.5]


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        confusion([0.1], [], 0.35)
    with pytest.raises(ValueError):
        confusion([0.1, 0.2], [1, 2], 0.35)
    with pytest.raises(ValueError):
        confusion([0.1], [0], 0.35)  # no genuine pairs
    with pytest.raises(ValueError):
        confusion([0.1], [1], 0.35)  # no impostor pairs
