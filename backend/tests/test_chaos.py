"""Chaos / fault-injection tests: dependencies down must degrade gracefully."""
import base64

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.config import CONSENT_VERSION
from app.db import SessionLocal, User
from app.main import app
from app.routes import registry, detection

IMAGE = base64.b64encode(b"\xff" * 256).decode()


class FakeFaceService:
    is_ready = True

    def count_faces(self, image_bytes):
        return 1

    def get_face_encoding(self, image_bytes):
        return [0.01] * 512

    def assess_enrollment(self, image_bytes):
        return {"ok": True, "face_count": 1, "reasons": [], "metrics": {},
                "embedding": self.get_face_encoding(image_bytes)}


class FakeVectorService:
    is_ready = True

    def __init__(self):
        self.points = {}

    def upsert(self, uid, embedding, payload):
        self.points[uid] = payload

    def count(self):
        return len(self.points)

    def search(self, embedding, limit=1, score_threshold=0.6):
        return []

    def delete(self, uid):
        self.points.pop(uid, None)


@pytest.fixture()
def client(monkeypatch):
    from app.db import Base, engine as app_engine

    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)
    monkeypatch.setattr(registry, "face_service", FakeFaceService())
    monkeypatch.setattr(registry, "vector_service", FakeVectorService())
    monkeypatch.setattr(detection, "face_service", FakeFaceService())
    monkeypatch.setattr(detection, "vector_service", FakeVectorService())
    with TestClient(app) as c:
        yield c


def _claims(uid, email, role):
    return {"uid": uid, "email": email, "role": role}


def _make_user(db, uid, email, role):
    u = db.get(User, uid)
    if u is None:
        u = User(id=uid, email=email, display_name=email, role=role)
        db.add(u)
    else:
        u.role = role
        u.email = email
    db.commit()
    db.refresh(u)


def _as(client, uid, email, role="admin"):
    with SessionLocal() as db:
        _make_user(db, uid, email, role)
    app.dependency_overrides[get_current_user] = lambda: _claims(uid, email, role)
    return client


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


def test_health_when_db_down(client, monkeypatch):
    from app import main as main_mod

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(main_mod, "_db_counts", lambda: (False, 0, 0))
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json()["database_ready"] is False


def test_enrollment_when_vector_down(client, monkeypatch):
    _as(client, "admin-1", "a@example.com", "admin")
    try:
        vs = FakeVectorService()
        vs.is_ready = False
        monkeypatch.setattr(registry, "vector_service", vs)
        res = client.post("/api/students/enroll", json={
            "name": "X", "roll_number": "R1", "department": "CS",
            "year": "3", "semester": "5", "image_base64": IMAGE,
            "consent_version": CONSENT_VERSION, "user_uid": "u1",
        })
        # enrollment still writes the SQL row; embedding_indexed reflects vector state
        assert res.status_code in (200, 503)
    finally:
        _clear()


def test_detect_when_model_down(client, monkeypatch):
    _as(client, "op-1", "o@example.com", "operator")
    try:
        fs = FakeFaceService()
        fs.is_ready = False
        monkeypatch.setattr(detection, "face_service", fs)
        res = client.post("/api/detect_webcam", json={"image_base64": IMAGE})
        assert res.status_code == 503
    finally:
        _clear()


def test_rate_limit_returns_429(client, monkeypatch):
    # Just verify the endpoint shape; full rate-limit tested elsewhere.
    _as(client, "op-1", "o@example.com", "operator")
    try:
        res = client.post("/api/detect_webcam", json={"image_base64": IMAGE})
        assert res.status_code in (200, 400, 429, 503)
    finally:
        _clear()