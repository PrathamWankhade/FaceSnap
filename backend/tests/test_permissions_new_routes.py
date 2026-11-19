"""Permission coverage for routes added after the initial matrix."""
import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import SessionLocal, User
from app.main import app


def _as_student(client, uid="perm-student"):
    with SessionLocal() as db:
        user = db.get(User, uid)
        if user is None:
            user = User(id=uid, email=f"{uid}@example.edu", display_name=uid, role="student")
            db.add(user)
        user.role = "student"
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": uid,
        "email": f"{uid}@example.edu",
        "role": "student",
    }
    return client


def _as_admin(client, uid="perm-admin"):
    with SessionLocal() as db:
        user = db.get(User, uid)
        if user is None:
            user = User(id=uid, email=f"{uid}@example.edu", display_name=uid, role="admin")
            db.add(user)
        user.role = "admin"
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": uid,
        "email": f"{uid}@example.edu",
        "role": "admin",
    }
    return client


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
    _clear()


# ---------------------------------------------------------------------------
# Staff-only routes must reject a student.
# ---------------------------------------------------------------------------
STAFF_ONLY = [
    ("GET", "/api/admin/model-info"),
    ("GET", "/api/audit/verify"),
    ("GET", "/api/reports/attendance"),
    ("GET", "/api/detections/review"),
    ("POST", "/api/detections/review/bulk-resolve"),
    ("POST", "/api/detections/review/bulk-dismiss"),
    ("GET", "/api/cameras"),
    ("POST", "/api/cameras"),
    ("GET", "/api/analytics/trends"),
]


@pytest.mark.parametrize("method,path", STAFF_ONLY)
def test_staff_only_routes_reject_student(client, method, path):
    _as_student(client)
    response = client.request(method, path, json={} if method == "POST" else None)
    assert response.status_code == 403, (method, path, response.status_code, response.text)
    _clear()


# Admin-only routes must reject a student but accept an admin.
def test_audit_verify_is_admin_only(client):
    _as_student(client)
    assert client.get("/api/audit/verify").status_code == 403
    _clear()

    _as_admin(client)
    # An empty audit chain verifies cleanly.
    assert client.get("/api/audit/verify").status_code == 200
    _clear()


# ---------------------------------------------------------------------------
# User-level routes are reachable by a student.
# ---------------------------------------------------------------------------
def test_liveness_challenge_is_user_level(client):
    _as_student(client)
    response = client.get("/api/liveness/challenge")
    assert response.status_code == 200
    body = response.json()
    assert body["challenge"] in {"blink", "turn_left", "turn_right"}
    assert body["token"]
    _clear()


def test_liveness_verify_challenge_is_user_level(client):
    _as_student(client)
    response = client.post(
        "/api/liveness/verify_challenge",
        json={"token": "not-a-token", "frames_base64": ["x" * 200] * 5, "frame_interval_ms": 100},
    )
    # The token is unknown, but the route itself is reachable (not 403).
    assert response.status_code in (200, 400)
    _clear()


def test_consent_report_is_admin_only(client):
    _as_student(client)
    assert client.get("/api/admin/consent-report").status_code == 403
    _clear()

    _as_admin(client)
    body = client.get("/api/admin/consent-report").json()
    assert body["currentVersion"]
    assert "byVersion" in body
    assert "stale" in body
    assert body["staleCount"] == len(body["stale"])
    _clear()


def test_consent_accept_requires_a_student_row(client):
    _as_student(client, uid="no-profile-student")
    response = client.post("/api/consent/accept")
    # No student row for this uid -> 404, not a permission failure.
    assert response.status_code == 404
    _clear()
