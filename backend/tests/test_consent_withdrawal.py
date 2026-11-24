"""Consent withdrawal, its gates, and deletion verification evidence."""
import base64

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.config import CONSENT_VERSION
from app.db import Base, SessionLocal, Student, User, engine
from app.main import app
from app.routes import registry

IMAGE = "data:image/jpeg;base64," + base64.b64encode(b"\xff" * 256).decode()


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(registry, "face_service", _FakeFaceService())
    monkeypatch.setattr(registry, "vector_service", _FakeVectorService())
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


def _as(client, uid="w-student", role="student"):
    with SessionLocal() as db:
        user = db.get(User, uid)
        if user is None:
            db.add(User(id=uid, email=f"{uid}@example.edu", display_name=uid, role=role))
        else:
            user.role = role
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": uid,
        "email": f"{uid}@example.edu",
        "role": role,
    }
    return client


def _enroll(client, uid="w-student"):
    res = client.post(
        "/api/students/enroll",
        json={
            "name": "Withdrawn Person",
            "roll_number": "W-1",
            "department": "CS",
            "year": "3",
            "semester": "5",
            "image_base64": IMAGE,
            "user_uid": uid,
            "consent_version": CONSENT_VERSION,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["student"]


class _FakeFaceService:
    is_ready = True

    def assess_enrollment(self, image_bytes):
        return {"ok": True, "face_count": 1, "metrics": {}, "embedding": [0.01] * 512}


class _FakeVectorService:
    is_ready = True

    def search(self, embedding, limit=1, score_threshold=0.6):
        return []

    def upsert(self, uid, embedding, payload):
        return None

    def delete(self, uid):
        return None


# ---------------------------------------------------------------------------
# Withdrawal lifecycle
# ---------------------------------------------------------------------------
def test_withdraw_is_recorded_and_idempotent(client):
    _as(client)
    _enroll(client)

    first = client.post("/api/consent/withdraw")
    assert first.status_code == 200
    assert first.json()["changed"] is True
    withdrawn_at = first.json()["withdrawnAt"]
    assert withdrawn_at

    second = client.post("/api/consent/withdraw")
    assert second.status_code == 200
    assert second.json()["changed"] is False
    assert second.json()["withdrawnAt"] == withdrawn_at

    me = client.get("/api/students/me").json()
    assert me["consentWithdrawnAt"] == withdrawn_at

    audit = None
    with SessionLocal() as db:
        from sqlalchemy import select

        from app.db import AuditLog

        audit = db.scalar(select(AuditLog).where(AuditLog.action == "consent.withdraw"))
    assert audit is not None


def test_withdrawal_blocks_enrollment_and_attendance(client):
    _as(client)
    student = _enroll(client)

    assert client.post("/api/consent/withdraw").status_code == 200

    # Re-enrollment (the most biometric operation) is refused.
    again = client.post(
        "/api/students/enroll",
        json={
            "name": "Withdrawn Person",
            "roll_number": "W-1",
            "department": "CS",
            "year": "3",
            "semester": "5",
            "image_base64": IMAGE,
            "consent_version": CONSENT_VERSION,
        },
    )
    assert again.status_code == 409
    assert "withdrawn" in again.json()["detail"]["message"].lower()

    # Biometric attendance is refused, not silently skipped.
    mark = client.post(
        "/api/attendance",
        json={"student_uid": student["uid"], "method": "individual_live"},
    )
    assert mark.status_code == 409
    assert "withdrawn" in mark.json()["detail"]["message"].lower()

    # Liveness verification is biometric processing too. The payload is valid
    # (registered image + 5 frames) so the 409 comes from the gate, not
    # validation.
    live = client.post(
        "/api/verify_liveness",
        json={
            "registered_image_base64": IMAGE,
            "frames_base64": [IMAGE] * 5,
            "frame_interval_ms": 100.0,
        },
    )
    assert live.status_code == 409
    assert "withdrawn" in live.json()["detail"]["message"].lower()


def test_re_accepting_consent_lifts_withdrawal(client):
    _as(client)
    student = _enroll(client)
    assert client.post("/api/consent/withdraw").status_code == 200

    accepted = client.post("/api/consent/accept")
    assert accepted.status_code == 200
    assert accepted.json()["changed"] is True
    assert accepted.json()["withdrawnAt"] is None
    assert client.get("/api/students/me").json()["consentWithdrawnAt"] is None

    # Attendance works again once consent is current.
    mark = client.post(
        "/api/attendance",
        json={"student_uid": student["uid"], "method": "individual_live"},
    )
    assert mark.status_code == 200


def test_withdrawal_refuses_when_no_profile(client):
    _as(client, "no-profile")
    assert client.post("/api/consent/withdraw").status_code == 404


# ---------------------------------------------------------------------------
# Deletion verification evidence
# ---------------------------------------------------------------------------
def test_delete_reports_per_store_evidence(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.FACE_IMAGE_DIR", str(tmp_path / "faces"))
    _as(client)
    student = _enroll(client)
    client.post(
        "/api/attendance",
        json={"student_uid": student["uid"], "method": "individual_live"},
    )

    res = client.delete(f"/api/students/{student['id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["deleted"] is True
    evidence = body["evidence"]
    assert evidence == {
        "photo": "deleted",
        "photoVerified": True,
        "embedding": "deleted",
        "attendanceRows": 1,
        "studentRow": "deleted",
        "verified": True,
    }

    assert client.get("/api/students/me").status_code == 404
    listed = client.get("/api/students").json()["students"]
    assert all(row["uid"] != body["uid"] for row in listed)


def test_delete_without_photo_reports_already_absent(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.FACE_IMAGE_DIR", str(tmp_path / "faces"))
    _as(client, "photo-less")
    with SessionLocal() as db:
        db.add(
            Student(
                id="s-noface",
                user_id="photo-less",
                name="No Photo",
                roll_number="NP-1",
                department="CS",
                year="1",
                semester="1",
            )
        )
        db.commit()

    res = client.delete("/api/students/s-noface")
    assert res.status_code == 200
    assert res.json()["evidence"]["photo"] == "already_absent"
    assert res.json()["evidence"]["attendanceRows"] == 0


def test_delete_vector_failure_is_reported_not_hidden(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.FACE_IMAGE_DIR", str(tmp_path / "faces"))
    _as(client)
    student = _enroll(client)

    def _boom(uid):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(registry.vector_service, "delete", _boom)

    res = client.delete(f"/api/students/{student['id']}")
    assert res.status_code == 200
    evidence = res.json()["evidence"]
    assert evidence["embedding"] == "delete failed"
    assert evidence["verified"] is False
    # The relational row is still gone: SQL is the system of record.
    assert evidence["studentRow"] == "deleted"


def test_student_cannot_delete_another_student(client):
    _as(client, "owner-a")
    owner = _enroll(client, "owner-a")
    _as(client, "intruder-b")
    res = client.delete(f"/api/students/{owner['id']}")
    assert res.status_code == 403