"""Regression tests for the anti-spoofing (rPPG) guard."""
import cv2
import numpy as np

from app.services.liveness_service import LivenessService


def _encode(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


def test_identical_stills_are_rejected_as_not_live():
    """A printed photo / paused video has no pulse and must not pass."""
    rng = np.random.default_rng(0)
    image = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)
    frame = _encode(image)

    result = LivenessService().detect_liveness([frame] * 30)

    assert result["live"] is False
    assert result["rppg_score"] == 0.0
    assert result["score"] < 0.5


def test_flat_colour_frames_are_rejected():
    frame = _encode(np.full((320, 320, 3), 120, dtype=np.uint8))
    result = LivenessService().detect_liveness([frame] * 12)

    assert result["live"] is False
    assert result["rppg_score"] == 0.0


def test_synthetic_pulse_is_accepted_as_live():
    """A genuine temporal signal (1.2 Hz on green) should pass liveness."""
    import math

    rng = np.random.default_rng(1)
    base = rng.integers(80, 180, (480, 640, 3), dtype=np.uint8)

    frames = []
    for i in range(30):
        frame = base.copy()
        factor = 1.0 + 0.02 * math.sin(2 * math.pi * 1.2 * i / 30.0)
        frame[:, :, 1] = np.clip(base[:, :, 1].astype(float) * factor, 0, 255).astype(np.uint8)
        frames.append(_encode(frame))

    result = LivenessService().detect_liveness(frames)

    assert result["live"] is True
    assert result["rppg_score"] > 0.5
