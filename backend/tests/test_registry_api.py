"""Integration tests for the relational registry API.

The face model and vector index are stubbed so these run fast and offline; the
database, object store, routing, auth resolution and idempotency rules are real.
"""
import base64

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.routes import registry

IMAGE = base64.b64encode(b"\xff" * 256).decode()


class FakeFaceService:
    is_ready = True

    def count_faces(self, image_bytes):
        return 1

    def get_face_encoding(self, image_bytes):
        return [0.01] * 512


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


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(registry, "face_service", FakeFaceService())
    monkeypatch.setattr(registry, "vector_service", FakeVectorService())

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def enroll(client, **overrides):
    payload = {
        "name": "Ada Lovelace",
        "roll_number": "CS2024-001",
        "department": "Computer Science",
        "year": "3",
        "semester": "5",
        "image_base64": IMAGE,
    }
    payload.update(overrides)
    return client.post("/api/students/enroll", json=payload)


def test_health_reports_database(client):
    body = client.get("/api/health").json()
    assert body["database_ready"] is True
    assert "students_in_db" in body


def test_enrollment_creates_student_and_profile(client):
    res = enroll(client)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] is True
    assert body["embedding_indexed"] is True
    assert body["student"]["rollNumber"] == "CS2024-001"

    listing = client.get("/api/students").json()
    assert listing["total"] == 1
    assert listing["students"][0]["uid"] == "dev"

    me = client.get("/api/me").json()
    assert me["role"] == "admin"
    assert me["student"]["name"] == "Ada Lovelace"

    # Enrollment photo is served to the owner only.
    face = client.get("/api/students/me/face")
    assert face.status_code == 200
    assert face.json()["image_base64"].startswith("data:image/jpeg;base64,")


def test_enrollment_is_an_upsert_not_a_duplicate(client):
    assert enroll(client).status_code == 200
    again = enroll(client, name="Ada L.", department="Information Technology")
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert client.get("/api/students").json()["total"] == 1


def test_roll_number_conflict_is_rejected(client):
    assert enroll(client).status_code == 200

    # A second account trying the same roll number gets a clean 409.
    from app.db import SessionLocal, User

    with SessionLocal() as db:
        db.add(User(id="someone-else", email="other@example.com", role="student"))
        db.commit()

    res = enroll(client, user_uid="someone-else")
    assert res.status_code == 409


def test_enrollment_rejects_multi_face_images(client, monkeypatch):
    class TwoFaces(FakeFaceService):
        def count_faces(self, image_bytes):
            return 2

    monkeypatch.setattr(registry, "face_service", TwoFaces())
    res = enroll(client)
    assert res.status_code == 422
    assert "exactly one" in res.json()["detail"]


def test_attendance_is_idempotent_per_method_and_day(client):
    assert enroll(client).status_code == 200

    first = client.post("/api/attendance", json={"method": "individual_live"})
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False

    second = client.post("/api/attendance", json={"method": "individual_live"})
    assert second.json()["duplicate"] is True
    assert second.json()["record"]["id"] == first.json()["record"]["id"]

    # A different capture path the same day is a distinct, legitimate record.
    third = client.post("/api/attendance", json={"method": "cctv_stream"})
    assert third.json()["duplicate"] is False

    records = client.get("/api/attendance").json()
    assert records["total"] == 2
    assert records["records"][0]["rollNumber"] == "CS2024-001"


def test_attendance_requires_a_student_profile(client):
    res = client.post("/api/attendance", json={"method": "individual_live"})
    assert res.status_code == 404


def test_attendance_for_unknown_session_is_404(client):
    assert enroll(client).status_code == 200
    res = client.post(
        "/api/attendance",
        json={"method": "individual_live", "session_id": 999},
    )
    assert res.status_code == 404


def test_sessions_and_session_scoped_attendance(client):
    created = client.post(
        "/api/sessions",
        json={"title": "Data Structures", "room": "B-204", "starts_at": "2026-10-23T09:00:00Z"},
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    assert enroll(client).status_code == 200
    first = client.post(
        "/api/attendance",
        json={"method": "doorway_batch", "session_id": session_id},
    )
    assert first.status_code == 200
    assert first.json()["duplicate"] is False

    again = client.post(
        "/api/attendance",
        json={"method": "cctv_stream", "session_id": session_id},
    )
    assert again.json()["duplicate"] is True

    listing = client.get("/api/sessions").json()
    assert listing["sessions"][0]["attendanceCount"] == 1


def test_summary_and_analytics(client):
    assert enroll(client).status_code == 200
    client.post("/api/attendance", json={"method": "individual_live"})
    client.post("/api/attendance", json={"method": "doorway_batch"})

    summary = client.get("/api/attendance/summary?days=7").json()
    assert summary["total"] == 2

    overview = client.get("/api/analytics/overview").json()
    assert overview["studentsTotal"] == 1
    assert overview["attendanceToday"] == 1  # distinct students, not rows
    assert overview["byMethod"]["individual_live"] == 1


def test_role_is_database_authoritative(client):
    me = client.get("/api/me").json()
    assert me["role"] == "admin"

    updated = client.patch("/api/users/dev/role", json={"role": "student"})
    assert updated.status_code == 200
    assert client.get("/api/me").json()["role"] == "student"

    # Non-admins cannot promote themselves.
    denied = client.patch("/api/users/dev/role", json={"role": "admin"})
    assert denied.status_code == 403


def test_delete_student_removes_profile(client):
    assert enroll(client).status_code == 200
    student_id = client.get("/api/students").json()["students"][0]["id"]

    deleted = client.delete(f"/api/students/{student_id}")
    assert deleted.status_code == 200
    assert client.get("/api/students").json()["total"] == 0
    assert client.get("/api/students/me").status_code == 404
