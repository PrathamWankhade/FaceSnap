"""Permission and IDOR integration tests for the registry API.

These run in dev-bypass mode (REQUIRE_AUTH=false) by overriding
``app.auth.get_current_user`` per request to authenticate as a chosen user.
The User row is pre-created in the test DB with the desired role, because
``resolve_user_row`` treats roles as database-authoritative.

Covers the matrix in docs/permissions.md: NFR-S1 (401/403 gating), NFR-S3
(no cross-user reads), and staff-only camera/matching routes.

401-in-production behaviour is covered by tests/test_security.py.
"""
import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import Attendance, SessionLocal, User
from app.main import app
from app.routes import registry

import base64

IMAGE = base64.b64encode(b"\xff" * 256).decode()  # > 100 chars, satisfies schema


@pytest.fixture(autouse=True)
def _clear_auth_overrides():
    """Guarantee dependency overrides never leak between tests in this file."""
    yield
    app.dependency_overrides.pop(get_current_user, None)


class FakeFaceService:
    is_ready = True

    def count_faces(self, image_bytes):
        return 1

    def get_face_encoding(self, image_bytes):
        return [0.01] * 512

    def get_multiple_encodings(self, frames_bytes):
        return [[0.01] * 512 for _ in frames_bytes]


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
    from app.db import Base, engine as app_engine

    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)

    monkeypatch.setattr(registry, "face_service", FakeFaceService())
    monkeypatch.setattr(registry, "vector_service", FakeVectorService())

    from app.main import app as test_app

    with TestClient(test_app) as test_client:
        yield test_client


def _claims(uid: str, email: str | None, role: str) -> dict:
    return {"uid": uid, "email": email, "role": role}


def _make_user(db, uid: str, email: str | None, role: str) -> User:
    user = db.get(User, uid)
    if user is None:
        user = User(id=uid, email=email, display_name=email, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.role = role
        user.email = email
        db.commit()
    return user


def _as(client: TestClient, uid: str, email: str | None, role: str = "student"):
    """Authenticate subsequent requests as ``uid`` (role comes from the DB row)."""
    with SessionLocal() as db:
        _make_user(db, uid, email, role)
    app.dependency_overrides[get_current_user] = lambda: _claims(uid, email, role)
    return client


def _clear(client: TestClient):
    app.dependency_overrides.pop(get_current_user, None)


def _enroll_student(client, uid, email, roll):
    """Enroll ``uid`` as a student, returning the student row id."""
    res = client.post(
        "/api/students/enroll",
        json={
            "user_uid": uid,
            "name": email.split("@")[0],
            "roll_number": roll,
            "department": "Computer Science",
            "year": "3",
            "semester": "5",
            "image_base64": IMAGE,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["student"]["id"]


# ---------------------------------------------------------------------------
# Role gating (NFR-S1)
# ---------------------------------------------------------------------------


def test_staff_routes_reject_students(client):
    _as(client, "student-a", "a@example.com", "student")
    try:
        for path, method, body in [
            ("/api/detect_webcam", "post", {"image_base64": IMAGE}),
            ("/api/analytics/overview", "get", None),
            ("/api/sessions", "post", {"title": "T", "starts_at": "2026-11-01T09:00:00Z"}),
            ("/api/pi/health", "get", None),
        ]:
            res = getattr(client, method)(path, json=body) if body else client.get(path)
            assert res.status_code == 403, f"{method.upper()} {path}: {res.text}"
    finally:
        _clear(client)


def test_operator_can_use_staff_routes(client):
    _as(client, "operator-1", "op@example.com", "operator")
    try:
        res = client.post("/api/sessions", json={"title": "Lab", "starts_at": "2026-11-01T09:00:00Z"})
        assert res.status_code == 200, res.text
        res = client.get("/api/analytics/overview")
        assert res.status_code == 200, res.text
    finally:
        _clear(client)


def test_admin_can_patch_roles(client):
    _as(client, "admin-1", "admin@example.com", "admin")
    try:
        _make_user(SessionLocal(), "target-1", "target@example.com", "student")
        res = client.patch("/api/users/target-1/role", json={"role": "operator"})
        assert res.status_code == 200, res.text
        assert res.json()["role"] == "operator"
    finally:
        _clear(client)


# ---------------------------------------------------------------------------
# IDOR / self-scoping (NFR-S3)
# ---------------------------------------------------------------------------


def test_student_list_shows_only_own_profile(client):
    _as(client, "student-a", "a@example.com", "student")
    id_a = _enroll_student(client, "student-a", "a@example.com", "CS2024-001")
    _as(client, "student-b", "b@example.com", "student")
    id_b = _enroll_student(client, "student-b", "b@example.com", "CS2024-002")
    # Back to A: A must not see B's row.
    _as(client, "student-a", "a@example.com", "student")
    listing = client.get("/api/students").json()
    assert listing["total"] == 1
    assert listing["students"][0]["id"] == id_a
    assert all(s["id"] != id_b for s in listing["students"])


def test_student_cannot_fetch_another_students_photo(client):
    _as(client, "student-a", "a@example.com", "student")
    _enroll_student(client, "student-a", "a@example.com", "CS2024-001")
    _as(client, "student-b", "b@example.com", "student")
    id_b = _enroll_student(client, "student-b", "b@example.com", "CS2024-002")
    # A fetches A's own photo -> OK.
    _as(client, "student-a", "a@example.com", "student")
    assert client.get("/api/students/me/face").status_code == 200
    # There is no "fetch by student id" endpoint; confirm B's photo is not
    # reachable through any list/me path (B never appears in A's listing).
    listing = client.get("/api/students").json()
    assert all(s["id"] != id_b for s in listing["students"])
    _clear(client)


def test_student_attendance_is_self_scoped(client):
    _as(client, "student-a", "a@example.com", "student")
    id_a = _enroll_student(client, "student-a", "a@example.com", "CS2024-001")
    _as(client, "student-b", "b@example.com", "student")
    id_b = _enroll_student(client, "student-b", "b@example.com", "CS2024-002")

    # Write attendance directly for both students (bypassing API gating).
    with SessionLocal() as db:
        db.add_all(
            [
                Attendance(student_id=id_a, method="individual_live"),
                Attendance(student_id=id_b, method="individual_live"),
            ]
        )
        db.commit()

    _as(client, "student-a", "a@example.com", "student")
    try:
        records = client.get("/api/attendance").json()
        assert records["total"] == 1
        assert records["records"][0]["studentId"] == id_a
    finally:
        _clear(client)


def test_student_cannot_enroll_another_account(client):
    _as(client, "admin-1", "admin@example.com", "admin")
    _make_user(SessionLocal(), "victim", "victim@example.com", "student")
    _clear(client)

    _as(client, "student-a", "a@example.com", "student")
    try:
        res = client.post(
            "/api/students/enroll",
            json={
                "user_uid": "victim",
                "name": "Hijack",
                "roll_number": "CS2024-999",
                "department": "CS",
                "year": "3",
                "semester": "5",
                "image_base64": IMAGE,
            },
        )
        assert res.status_code == 403, res.text
    finally:
        _clear(client)


def test_student_cannot_delete_another_student(client):
    _as(client, "student-a", "a@example.com", "student")
    _enroll_student(client, "student-a", "a@example.com", "CS2024-001")
    _as(client, "student-b", "b@example.com", "student")
    id_b = _enroll_student(client, "student-b", "b@example.com", "CS2024-002")
    _as(client, "student-a", "a@example.com", "student")
    try:
        res = client.delete(f"/api/students/{id_b}")
        assert res.status_code == 403, res.text
        # B still exists.
        _as(client, "student-b", "b@example.com", "student")
        assert client.get("/api/students/me").status_code == 200
    finally:
        _clear(client)


def test_admin_sees_all_students(client):
    _as(client, "admin-1", "admin@example.com", "admin")
    id_a = _enroll_student(client, "student-a", "a@example.com", "CS2024-001")
    _as(client, "student-b", "b@example.com", "student")
    id_b = _enroll_student(client, "student-b", "b@example.com", "CS2024-002")
    _as(client, "admin-1", "admin@example.com", "admin")
    try:
        listing = client.get("/api/students").json()
        assert listing["total"] == 2
        assert {s["id"] for s in listing["students"]} == {id_a, id_b}
    finally:
        _clear(client)


def test_session_creation_requires_staff(client):
    _as(client, "student-a", "a@example.com", "student")
    try:
        res = client.post(
            "/api/sessions",
            json={"title": "Lab", "starts_at": "2026-11-01T09:00:00Z"},
        )
        assert res.status_code == 403, res.text
    finally:
        _clear(client)


def test_leave_is_scoped_to_own_student(client):
    # Create a session for leave to reference (staff).
    _as(client, "admin-1", "admin@example.com", "admin")
    session = client.post(
        "/api/sessions",
        json={"title": "Lab", "starts_at": "2026-11-01T09:00:00Z"},
    )
    session_id = session.json()["id"]
    _clear(client)

    _as(client, "student-a", "a@example.com", "student")
    _enroll_student(client, "student-a", "a@example.com", "CS2024-001")
    # A can create leave for themself.
    res = client.post("/api/leave", json={"session_id": session_id, "reason": "ill"})
    assert res.status_code == 200, res.text
    # A's list shows only A's leave.
    mine = client.get("/api/leave").json()
    assert len(mine["requests"]) == 1
    _clear(client)
