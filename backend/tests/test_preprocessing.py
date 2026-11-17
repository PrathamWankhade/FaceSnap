"""Low-light preprocessing: conditional, deterministic, and testable without faces.

No biometric data is used here; images are synthetic gradients generated in the
test itself.
"""
import numpy as np
import pytest

from app.services.face_service import enhance_low_light


def _gradient(mean_target: int, size: int = 64) -> np.ndarray:
    """A smooth BGR gradient whose grayscale mean is close to ``mean_target``."""
    ramp = np.linspace(0.0, 1.0, size, dtype=np.float32)
    base = np.tile(ramp, (size, 1))
    # Scale so the mean lands on the requested value.
    base = base * (2.0 * mean_target) / max(float(base.mean()), 1e-6)
    base = np.clip(base, 0, 255).astype(np.uint8)
    return np.dstack([base, base, base])


def test_bright_image_is_returned_untouched():
    image = _gradient(150)
    before = image.copy()
    out, meta = enhance_low_light(image)
    assert meta["applied"] is False
    assert meta["gamma"] == 1.0
    assert np.array_equal(out, before)


def test_dark_image_is_lifted_toward_the_target():
    image = _gradient(35)
    before_mean = float(image.mean())
    out, meta = enhance_low_light(image)

    assert meta["applied"] is True
    assert meta["gamma"] > 1.0
    assert meta["input_mean"] == pytest.approx(before_mean, abs=1.0)
    assert out.mean() > before_mean
    # The return type/range stays a valid 8-bit BGR image.
    assert out.dtype == np.uint8
    assert out.shape == image.shape


def test_gamma_gain_is_capped_for_near_black_frames():
    image = np.full((32, 32, 3), 2, dtype=np.uint8)
    out, meta = enhance_low_light(image)
    assert meta["applied"] is True
    assert 1.0 <= meta["gamma"] <= 3.0
    # Capped gain must not turn a near-black frame into a blown-out white frame.
    assert out.mean() < 160


def test_empty_image_is_rejected():
    with pytest.raises(ValueError):
        enhance_low_light(np.zeros((0, 0, 3), dtype=np.uint8))
