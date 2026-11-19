"""Camera registry permissions and attendance trend bucketing."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import Attendance, Base, SessionLocal, Student, User, engine, utcnow
from app.main import app
from app.routes.registry import _trend_period


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


def _as(client, uid, email, role):
    with SessionLocal() as db:
        user = db.get(User, uid)
        if user is None:
            user = User(id=uid, email=email, display_name=email, role=role)
            db.add(user)
        user.role = role
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: {"uid": uid, "email": email, "role": role}
    return client


def _seed_student(department: str = "Computer Science") -> str:
    with SessionLocal() as db:
        user = User(id="stu-1", email="stu1@example.edu", display_name="Student One", role="student")
        db.add(user)
        db.flush()
        student = Student(
            id="student-1",
            user_id=user.id,
            name="Student One",
            roll_number="CS-001",
            department=department,
            year="2",
            semester="3",
        )
        db.add(student)
        db.commit()
    return student.id


# ---------------------------------------------------------------------------
# Camera registry
# ---------------------------------------------------------------------------
def test_students_cannot_read_or_change_cameras(client):
    _as(client, "stu-cam", "stu-cam@example.edu", "student")

    assert client.get("/api/cameras").status_code == 403
    assert client.post("/api/cameras", json={"name": "Door 1"}).status_code == 403
    assert client.delete("/api/cameras/1").status_code == 403


def test_staff_can_create_list_and_delete_cameras(client):
    _as(client, "admin-cam", "admin-cam@example.edu", "admin")

    created = client.post(
        "/api/cameras",
        json={"name": "Main Gate", "location": "Gate", "stream_url": "rtsp://camera.local/1"},
    )
    assert created.status_code == 200
    camera_id = created.json()["id"]

    listing = client.get("/api/cameras").json()["cameras"]
    assert len(listing) == 1
    assert listing[0]["id"] == camera_id
    assert listing[0]["streamUrl"] == "rtsp://camera.local/1"
    assert listing[0]["status"] == "offline"

    assert client.delete(f"/api/cameras/{camera_id}").json()["deleted"] is True
    assert client.get("/api/cameras").json()["cameras"] == []
    assert client.delete(f"/api/cameras/{camera_id}").status_code == 404


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------
def test_week_bucket_handles_the_start_of_a_month():
    # 1 Jan 2026 is a Thursday: day(1) - weekday(3) is negative, which used to
    # raise inside date.replace(). The week must start on Monday, 29 Dec 2025.
    assert _trend_period(datetime(2026, 1, 1, 9, 0), "week") == "2025-12-29"
    assert _trend_period(datetime(2026, 1, 1, 9, 0), "day") == "2026-01-01"
    assert _trend_period(datetime(2026, 1, 1, 9, 0), "month") == "2026-01"


def test_trends_are_staff_only(client):
    _as(client, "stu-trends", "stu-trends@example.edu", "student")
    assert client.get("/api/analytics/trends").status_code == 403


def test_trends_bucket_attendance_by_day_and_method(client):
    student_id = _seed_student()
    with SessionLocal() as db:
        now = utcnow()
        db.add_all(
            [
                Attendance(student_id=student_id, captured_at=now, method="individual_live"),
                Attendance(student_id=student_id, captured_at=now - timedelta(days=2), method="cctv_stream"),
            ]
        )
        db.commit()

    _as(client, "admin-trends", "admin-trends@example.edu", "admin")
    body = client.get("/api/analytics/trends", params={"group": "day", "days": 7}).json()

    assert body["total"] == 2
    assert len(body["series"]) == 2
    methods = sorted(method for bucket in body["series"] for method in bucket["byMethod"])
    assert methods == ["cctv_stream", "individual_live"]
    assert sum(bucket["total"] for bucket in body["series"]) == 2


def test_trends_department_filter_excludes_other_departments(client):
    _seed_student(department="Mechanical")
    with SessionLocal() as db:
        db.add(Attendance(student_id="student-1", captured_at=utcnow(), method="individual_live"))
        db.commit()

    _as(client, "admin-trends-2", "admin-trends-2@example.edu", "admin")
    body = client.get(
        "/api/analytics/trends",
        params={"group": "day", "days": 7, "department": "Computer Science"},
    ).json()

    assert body["total"] == 0
    assert body["series"] == []
