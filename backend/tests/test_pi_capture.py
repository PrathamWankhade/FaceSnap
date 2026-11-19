"""Shared camera-frame capture, including the anonymize option."""
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.routes import pi_routes


def _fake_camera(monkeypatch):
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)
    monkeypatch.setattr(pi_routes.pi_camera, "read", lambda: (True, frame))


def test_capture_returns_jpeg_frame(monkeypatch):
    _fake_camera(monkeypatch)
    with TestClient(app) as client:
        res = client.get("/api/pi/capture")
    assert res.status_code == 200
    assert res.json()["image_base64"]


def test_capture_anonymize_blurs_detected_faces(monkeypatch):
    _fake_camera(monkeypatch)
    calls = []
    monkeypatch.setattr(
        type(pi_routes.face_service),
        "detect_face_boxes",
        lambda self, data: calls.append(len(data)) or [(0, 0, 32, 32)],
    )
    with TestClient(app) as client:
        plain = client.get("/api/pi/capture").json()["image_base64"]
        anon = client.get("/api/pi/capture?anonymize=true").json()["image_base64"]

    # Detection runs only for the anonymized fetch, and the bytes differ.
    assert len(calls) == 1
    assert plain != anon


def test_capture_without_faces_returns_original_bytes(monkeypatch):
    _fake_camera(monkeypatch)
    monkeypatch.setattr(type(pi_routes.face_service), "detect_face_boxes", lambda self, data: [])
    with TestClient(app) as client:
        plain = client.get("/api/pi/capture").json()["image_base64"]
        anon = client.get("/api/pi/capture?anonymize=true").json()["image_base64"]
    assert plain == anon
