"""Regression tests for the anti-spoofing (rPPG) guard."""
import time

import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from app.models.schemas import LivenessVerifyRequest
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

    # 30 frames sampled at 30 FPS (the signal above is defined in frame units).
    result = LivenessService().detect_liveness(frames, fps=30)

    assert result["live"] is True
    assert result["rppg_score"] > 0.5


def test_synthetic_pulse_uses_the_measured_sample_rate():
    """The same pulse must be found when the client reports a 10 FPS capture.

    The frontend records ~5 seconds at 10 FPS; analysing those frames with an
    assumed 30 FPS would place a 1.2 Hz pulse below the heartbeat band and
    wrongly reject a live face.
    """
    import math

    rng = np.random.default_rng(2)
    base = rng.integers(80, 180, (240, 320, 3), dtype=np.uint8)

    frames = []
    for i in range(50):
        frame = base.copy()
        factor = 1.0 + 0.02 * math.sin(2 * math.pi * 1.2 * i / 10.0)
        frame[:, :, 1] = np.clip(base[:, :, 1].astype(float) * factor, 0, 255).astype(np.uint8)
        frames.append(_encode(frame))

    service = LivenessService()
    measured = service.detect_liveness(frames, fps=10)
    assert measured["live"] is True
    assert measured["rppg_score"] > 0.5
    assert measured["fps"] == 10.0

    # With a wrong (too high) assumed rate the pulse falls outside the band.
    wrong = service.detect_liveness(frames, fps=30)
    assert wrong["rppg_score"] < measured["rppg_score"]


def test_liveness_request_validates_frame_interval():
    base = {
        "registered_image_base64": "x" * 200,
        "frames_base64": ["y" * 200] * 5,
    }

    default = LivenessVerifyRequest(**base)
    assert default.frame_interval_ms == 100.0

    assert LivenessVerifyRequest(**base, frame_interval_ms=1000).frame_interval_ms == 1000.0

    with pytest.raises(ValidationError):
        LivenessVerifyRequest(**base, frame_interval_ms=5)
    with pytest.raises(ValidationError):
        LivenessVerifyRequest(**base, frame_interval_ms=2000)


def _flat_frames(count: int = 12) -> list[bytes]:
    frame = _encode(np.full((64, 64, 3), 110, dtype=np.uint8))
    return [frame] * count


def test_challenge_tokens_are_single_use():
    service = LivenessService()
    issued = service.issue_challenge()

    first = service.verify_challenge(_flat_frames(), issued["token"])
    # The token was accepted, so the challenge name comes back even though the
    # flat frames fail the underlying liveness bar.
    assert first["challenge"] == issued["challenge"]
    assert first["passed"] is False

    second = service.verify_challenge(_flat_frames(), issued["token"])
    assert second["passed"] is False
    assert "unknown or expired" in second["reason"]


def test_expired_challenge_is_rejected(monkeypatch):
    service = LivenessService()
    issued = service.issue_challenge()
    started = time.monotonic()
    monkeypatch.setattr(
        "app.services.liveness_service.time.monotonic",
        lambda: started + service.CHALLENGE_TTL_SECONDS + 1,
    )

    result = service.verify_challenge(_flat_frames(), issued["token"])

    assert result["passed"] is False
    assert result["reason"] == "challenge expired"


def test_pending_challenges_are_capped():
    service = LivenessService()
    for _ in range(service.MAX_PENDING_CHALLENGES + 25):
        service.issue_challenge()

    assert len(service._challenges) <= service.MAX_PENDING_CHALLENGES
