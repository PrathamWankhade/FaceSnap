"""Enrollment quality gates: one detection pass decides accept/reject.

Uses synthetic images and a stub detector, so no face data or model download is
involved. The point is the decision logic and its measurable reasons.
"""
import numpy as np
import pytest

from app.services.face_service import FaceService


class _Face:
    def __init__(self, bbox, embedding, det_score=0.99, kps=None):
        self.bbox = np.asarray(bbox, dtype=np.float32)
        self.embedding = embedding
        self.det_score = det_score
        self.kps = np.asarray(kps, dtype=np.float32) if kps is not None else None


class _Detector:
    def __init__(self, faces):
        self.faces = faces

    def get(self, _rgb):
        return list(self.faces)


def _service(faces):
    service = FaceService.__new__(FaceService)  # skip model loading
    service.app = _Detector(faces)
    return service


def _encode(image):
    import cv2

    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


def _frontal_kps(x=200, y=180, nose_x=200):
    return [
        (x - 50, y),
        (x + 50, y),
        (nose_x, y + 40),
        (x - 35, y + 90),
        (x + 35, y + 90),
    ]


def _sharp_image(size=400):
    """A checkerboard has high Laplacian variance and mid luminance."""
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[::8, ::8] = 255
    image[4::8, 4::8] = 255
    return image


def _embedding(seed=0):
    vector = np.random.default_rng(seed).random(512).astype(np.float32)
    return vector / np.linalg.norm(vector)


def _good_face(**overrides):
    values = {
        "bbox": [100, 100, 300, 300],
        "embedding": _embedding(),
        "det_score": 0.99,
        "kps": _frontal_kps(),
    }
    values.update(overrides)
    return _Face(**values)


def test_good_frontal_photo_is_accepted_with_a_normalised_embedding():
    service = _service([_good_face()])
    result = service.assess_enrollment(_encode(_sharp_image()))

    assert result["ok"] is True, result["reasons"]
    assert result["face_count"] == 1
    assert result["metrics"]["face_width"] == 200
    assert result["metrics"]["sharpness"] > 0
    embedding = np.asarray(result["embedding"], dtype=np.float32)
    assert embedding.shape == (512,)
    assert float(np.linalg.norm(embedding)) == pytest.approx(1.0, abs=1e-5)


def test_multiple_faces_are_rejected_without_an_embedding():
    service = _service([_good_face(), _good_face()])
    result = service.assess_enrollment(_encode(_sharp_image()))

    assert result["ok"] is False
    assert result["face_count"] == 2
    assert result["embedding"] is None
    assert any("exactly one" in reason for reason in result["reasons"])


def test_tiny_face_is_rejected():
    service = _service([_good_face(bbox=[100, 100, 140, 140])])
    result = service.assess_enrollment(_encode(_sharp_image()))

    assert result["ok"] is False
    assert any("too small" in reason for reason in result["reasons"])


def test_blurry_photo_is_rejected():
    service = _service([_good_face()])
    flat = np.full((400, 400, 3), 128, dtype=np.uint8)
    result = service.assess_enrollment(_encode(flat))

    assert result["ok"] is False
    assert result["metrics"]["sharpness"] < 1
    assert any("blurry" in reason for reason in result["reasons"])


def test_low_detection_confidence_is_rejected():
    service = _service([_good_face(det_score=0.3)])
    result = service.assess_enrollment(_encode(_sharp_image()))

    assert result["ok"] is False
    assert any("not clear enough" in reason for reason in result["reasons"])


def test_turned_head_is_rejected_by_the_landmark_screen():
    service = _service([_good_face(kps=_frontal_kps(nose_x=290))])
    result = service.assess_enrollment(_encode(_sharp_image()))

    assert result["ok"] is False
    assert result["metrics"]["yaw_ratio"] > 0.5
    assert any("turned too far" in reason for reason in result["reasons"])


def test_missing_pose_landmarks_do_not_block_a_clear_face():
    service = _service([_good_face(kps=None)])
    result = service.assess_enrollment(_encode(_sharp_image()))

    assert result["ok"] is True, result["reasons"]
    assert result["metrics"]["yaw_ratio"] is None


def test_wrong_embedding_size_is_rejected():
    service = _service([_good_face(embedding=[0.1] * 10)])
    result = service.assess_enrollment(_encode(_sharp_image()))

    assert result["ok"] is False
    assert result["embedding"] is None
    assert any("embedding" in reason for reason in result["reasons"])


def test_unreadable_image_is_a_clean_rejection():
    service = _service([_good_face()])
    result = service.assess_enrollment(b"not-an-image")

    assert result["ok"] is False
    assert result["face_count"] == 0
    assert result["reasons"]
