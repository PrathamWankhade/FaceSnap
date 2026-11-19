"""Tests for sprint features: alerting, review queue, drift histogram, model version, CSV reports."""
import base64

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.config import CONSENT_VERSION
from app.db import Base, SessionLocal, User, engine
from app.main import app
from app.metrics import Metrics
from app.routes import detection, registry
from app.services import notifier

IMAGE = base64.b64encode(b"\xff" * 256).decode()


class FakeFaceService:
    is_ready = True

    def count_faces(self, image_bytes):
        return 1

    def get_face_encoding(self, image_bytes):
        return [0.01] * 512

    def assess_enrollment(self, image_bytes):
        return {
            "ok": True,
            "face_count": 1,
            "reasons": [],
            "metrics": {},
            "embedding": self.get_face_encoding(image_bytes),
        }


class FakeVectorService:
    is_ready = True

    def __init__(self):
        self.points = {}

    def upsert(self, uid, embedding, payload):
        self.points[uid] = payload

    def delete(self, uid):
        self.points.pop(uid, None)

    def count(self):
        return len(self.points)

    def search(self, embedding, limit=1, score_threshold=0.6):
        return []


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(registry, "face_service", FakeFaceService())
    monkeypatch.setattr(registry, "vector_service", FakeVectorService())
    monkeypatch.setattr(detection, "face_service", FakeFaceService())
    monkeypatch.setattr(detection, "vector_service", FakeVectorService())

    with TestClient(app) as test_client:
        yield test_client


def _claims(uid, email, role):
    return {"uid": uid, "email": email, "role": role}


def _make_user(db, uid, email, role):
    user = db.get(User, uid)
    if user is None:
        user = User(id=uid, email=email, display_name=email, role=role)
        db.add(user)
    else:
        user.role = role
        user.email = email
    db.commit()
    db.refresh(user)
    return user


def _as(client, uid, email, role="student"):
    with SessionLocal() as db:
        _make_user(db, uid, email, role)
    app.dependency_overrides[get_current_user] = lambda: _claims(uid, email, role)
    return client


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Notifier
# ---------------------------------------------------------------------------
def test_notifier_disabled_without_webhook(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_WEBHOOK_URL", "")
    notifier.reset_cooldowns()
    assert notifier.notify("x", {"a": 1}) is False


def test_notifier_delivers_when_configured(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_WEBHOOK_URL", "http://example.test/hook")
    monkeypatch.setattr(notifier, "ALERT_COOLDOWN_SECONDS", 0)
    notifier.reset_cooldowns()
    calls = []

    def fake_deliver(url, payload):
        calls.append((url, payload))
        return True

    monkeypatch.setattr(notifier, "_deliver", fake_deliver)
    assert notifier.notify("health_degraded", {"components": {"database": False}}) is True
    assert len(calls) == 1
    assert calls[0][1]["event"] == "health_degraded"


def test_notifier_cooldown_suppresses_repeat(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_WEBHOOK_URL", "http://example.test/hook")
    monkeypatch.setattr(notifier, "ALERT_COOLDOWN_SECONDS", 10_000)
    notifier.reset_cooldowns()
    monkeypatch.setattr(notifier, "_deliver", lambda url, payload: True)
    assert notifier.notify("e", {}) is True
    assert notifier.notify("e", {}) is False


def test_notifier_health_degraded_only_when_hard_dep_down(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_WEBHOOK_URL", "http://example.test/hook")
    monkeypatch.setattr(notifier, "ALERT_COOLDOWN_SECONDS", 0)
    notifier.reset_cooldowns()
    monkeypatch.setattr(notifier, "_deliver", lambda url, payload: True)
    assert notifier.health_degraded({"database": True, "vector_db": True, "face_model": True, "camera": False}) is False
    assert notifier.health_degraded({"database": False, "vector_db": True, "face_model": True, "camera": False}) is True


def test_notifier_error_rate_spike_respects_min_samples(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_WEBHOOK_URL", "http://example.test/hook")
    monkeypatch.setattr(notifier, "ALERT_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(notifier, "ALERT_MIN_REQUESTS", 5)
    monkeypatch.setattr(notifier, "ALERT_ERROR_RATE_THRESHOLD", 0.5)
    notifier.reset_cooldowns()
    monkeypatch.setattr(notifier, "_deliver", lambda url, payload: True)
    assert notifier.error_rate_spike(total=3, failures=3) is False
    assert notifier.error_rate_spike(total=10, failures=6) is True


# ---------------------------------------------------------------------------
# Metrics drift histogram
# ---------------------------------------------------------------------------
def test_metrics_match_distance_render():
    registry = Metrics()
    registry.record_match_distance(0.12, route="/api/pi/detect")
    registry.record_match_distance(0.4, route="/api/pi/detect")
    text = registry.render()
    assert "facesnap_match_distance_bucket" in text
    assert 'route="/api/pi/detect"' in text
    assert "facesnap_match_distance_count" in text


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------
def test_review_queue_requires_staff(client):
    _as(client, "student-a", "a@example.com", "student")
    try:
        res = client.get("/api/detections/review")
        assert res.status_code == 403
    finally:
        _clear()


def test_review_queue_list_and_resolve(client):
    _as(client, "op-1", "op@example.com", "operator")
    try:
        # create an item directly
        from app.db import DetectionReview, SessionLocal

        with SessionLocal() as db:
            db.add(DetectionReview(status="pending", nearest_uid="u1", nearest_distance=0.4))
            db.commit()
            item_id = db.query(DetectionReview).first().id

        res = client.get("/api/detections/review")
        assert res.status_code == 200
        assert res.json()["total"] >= 1

        res = client.patch(f"/api/detections/review/{item_id}", json={"status": "resolved", "note": "ok"})
        assert res.status_code == 200
        assert res.json()["status"] == "resolved"
        assert res.json()["note"] == "ok"

        # Per-item audit trail: resolve wrote a detection_review audit row.
        res = client.get(f"/api/detections/review/{item_id}/history")
        assert res.status_code == 200
        body = res.json()
        assert body["reviewId"] == item_id
        assert any(e["action"] == "detection.review.resolve" for e in body["events"])
        assert all("rowHash" in e and "createdAt" in e for e in body["events"])

        # Unknown item -> 404, not an empty list (a missing id is an error).
        res = client.get("/api/detections/review/999999999/history")
        assert res.status_code == 404
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Attendance CSV report
# ---------------------------------------------------------------------------
def test_attendance_report_csv(client):
    _as(client, "op-1", "op@example.com", "operator")
    try:
        res = client.get("/api/reports/attendance")
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert "attendance_id" in res.text
    finally:
        _clear()

    _as(client, "student-a", "a@example.com", "student")
    try:
        res = client.get("/api/reports/attendance")
        assert res.status_code == 403
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Model version on enroll
# ---------------------------------------------------------------------------
def test_model_version_recorded_on_enroll(client):
    _as(client, "student-a", "a@example.com", "student")
    try:
        res = client.post(
            "/api/students/enroll",
            json={
                "name": "Ada",
                "roll_number": "CS-1",
                "department": "CS",
                "year": "3",
                "semester": "5",
                "image_base64": IMAGE,
                "consent_version": CONSENT_VERSION,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["student"]["modelVersion"] is not None
    finally:
        _clear()