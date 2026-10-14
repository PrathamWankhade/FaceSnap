"""Unit tests for face matching math (no model weights required)."""
import math
import sys
import types

import numpy as np

# face_service imports cv2 at module load; stub it when OpenCV isn't installed (CI math tests).
if "cv2" not in sys.modules:
    try:
        import cv2  # noqa: F401
    except Exception:
        sys.modules["cv2"] = types.ModuleType("cv2")

from app.services.face_service import FaceService

svc = FaceService.__new__(FaceService)  # skip model load


def _unit(dim=512, seed=0):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=dim).astype(np.float64)
    return (v / np.linalg.norm(v)).tolist()


def test_identical_embeddings_match():
    e = _unit()
    match, score, dist = FaceService.verify_faces(svc, e, list(e))
    assert match is True
    assert dist == 0.0
    assert score > 90


def test_list_vs_array_same_distance():
    e = _unit(seed=1)
    f = _unit(seed=2)
    m1 = FaceService.verify_faces(svc, e, f)
    m2 = FaceService.verify_faces(svc, np.asarray(e), np.asarray(f))
    assert m1[0] == m2[0]
    assert math.isclose(m1[2], m2[2], rel_tol=1e-6)


def test_shape_mismatch_rejected():
    e = _unit()
    match, score, dist = FaceService.verify_faces(svc, e, e[:128])
    assert match is False
    assert dist == 1.0


def test_zero_vector_rejected():
    e = _unit()
    z = [0.0] * 512
    match, _, _ = FaceService.verify_faces(svc, e, z)
    assert match is False


def test_far_embeddings_do_not_match():
    e = _unit(seed=3)
    f = [-x for x in e]  # opposite direction => distance ~2
    match, _, dist = FaceService.verify_faces(svc, e, f)
    assert match is False
    assert dist > 1.0
