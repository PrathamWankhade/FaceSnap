"""Relational API: enrollment, attendance, sessions, analytics.

All writes go through FastAPI so the database stays the single source of truth
(the browser no longer writes attendance directly).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user_row, require_roles
from app.db import (
    Attendance,
    AuditLog,
    Camera,
    ClassSession,
    Course,
    Department,
    LeaveRequest,
    Student,
    User,
    as_utc,
    get_db,
    to_naive_utc,
    utcnow,
)
from app.services import image_store
from app.services.face_service import face_service
from app.services.vector_service import vector_service

router = APIRouter()

CaptureMethod = Literal["individual_live", "doorway_batch", "cctv_stream", "upload"]

STAFF_ROLES = ("admin", "operator")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class EnrollRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    roll_number: str = Field(min_length=1, max_length=50)
    department: str = Field(min_length=1, max_length=120)
    year: str = Field(min_length=1, max_length=20)
    semester: str = Field(min_length=1, max_length=20)
    image_base64: str = Field(min_length=100, max_length=12_000_000)
    user_uid: str | None = Field(default=None, max_length=128)


class AttendanceCreate(BaseModel):
    student_uid: str | None = Field(default=None, max_length=128)
    session_id: int | None = None
    method: CaptureMethod
    liveness_score: float | None = Field(default=None, ge=0, le=1)
    distance: float | None = Field(default=None, ge=0)
    captured_at: datetime | None = None


class SessionCreate(BaseModel):
    course_code: str | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, max_length=160)
    room: str | None = Field(default=None, max_length=80)
    starts_at: datetime
    ends_at: datetime | None = None
    status: str = Field(default="scheduled", max_length=20)


class LeaveCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    session_id: int | None = None


class RoleUpdate(BaseModel):
    role: Literal["admin", "operator", "student"]


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
def _iso(value: datetime | None) -> str | None:
    dt = as_utc(value)
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def student_dict(student: Student) -> dict:
    return {
        "id": student.id,
        "uid": student.user_id,
        "email": student.user.email if student.user else None,
        "name": student.name,
        "rollNumber": student.roll_number,
        "roll_no": student.roll_number,
        "department": student.department,
        "year": student.year,
        "semester": student.semester,
        "registeredAt": _iso(student.enrolled_at),
        "hasFaceImage": bool(student.face_image_key),
    }


def attendance_dict(record: Attendance) -> dict:
    student = record.student
    return {
        "id": record.id,
        "studentUid": student.user_id,
        "studentId": record.student_id,
        "name": student.name,
        "studentName": student.name,
        "rollNumber": student.roll_number,
        "rollNo": student.roll_number,
        "department": student.department,
        "year": student.year,
        "semester": student.semester,
        "timestamp": _iso(record.captured_at),
        "method": record.method,
        "liveness_score": record.liveness_score,
        "sessionId": record.session_id,
        "cameraId": record.camera_id,
        "distance": record.distance,
    }


def _audit(db: Session, actor: User, action: str, entity: str, entity_id: str | int | None) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, entity=entity, entity_id=str(entity_id)))


def _student_for_user(db: Session, uid: str) -> Student | None:
    return db.scalar(select(Student).where(Student.user_id == uid))


def _require_student(db: Session, uid: str) -> Student:
    student = _student_for_user(db, uid)
    if student is None:
        raise HTTPException(status_code=404, detail="No student profile for this account.")
    return student


def _day_bounds(value: datetime) -> tuple[datetime, datetime]:
    naive = to_naive_utc(value) or utcnow()
    start = naive.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


# ---------------------------------------------------------------------------
# Identity / profile
# ---------------------------------------------------------------------------
@router.get("/api/me")
def me(user: User = Depends(get_current_user_row), db: Session = Depends(get_db)):
    student = _student_for_user(db, user.id)
    return {
        "uid": user.id,
        "email": user.email,
        "displayName": user.display_name,
        "role": user.role,
        "student": student_dict(student) if student else None,
    }


@router.patch("/api/users/{uid}/role")
def set_role(
    uid: str,
    payload: RoleUpdate,
    actor: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    target = db.get(User, uid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    target.role = payload.role
    _audit(db, actor, "role.update", "user", uid)
    db.commit()
    return {"uid": target.id, "role": target.role}


# ---------------------------------------------------------------------------
# Students / enrollment
# ---------------------------------------------------------------------------
@router.post("/api/students/enroll")
def enroll(
    payload: EnrollRequest,
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
):
    if not face_service.is_ready:
        raise HTTPException(status_code=503, detail="Face recognition model not loaded.")

    target_uid = payload.user_uid or user.id
    if target_uid != user.id and user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Only staff can enroll another account.")

    try:
        image_bytes = image_store.decode_data_url(payload.image_base64)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    face_count = face_service.count_faces(image_bytes)
    if face_count != 1:
        raise HTTPException(
            status_code=422,
            detail="Enrollment needs exactly one clearly visible face "
                   f"(detected {face_count}).",
        )

    embedding = face_service.get_face_encoding(image_bytes)
    if embedding is None:
        raise HTTPException(status_code=422, detail="Could not extract a face embedding.")

    # Roll number is unique across the institution.
    clash = db.scalar(select(Student).where(Student.roll_number == payload.roll_number))
    if clash and clash.user_id != target_uid:
        raise HTTPException(status_code=409, detail="Roll number is already registered.")

    student = _student_for_user(db, target_uid)
    created = student is None
    if student is None:
        student = Student(
            id=str(uuid.uuid4()),
            user_id=target_uid,
            name=payload.name,
            roll_number=payload.roll_number,
            department=payload.department,
            year=payload.year,
            semester=payload.semester,
        )
        db.add(student)
    else:
        student.name = payload.name
        student.roll_number = payload.roll_number
        student.department = payload.department
        student.year = payload.year
        student.semester = payload.semester

    student.face_image_key = image_store.save(student.id, payload.image_base64)
    db.flush()

    vector_service.upsert(
        uid=target_uid,
        embedding=embedding,
        payload={
            "uid": target_uid,
            "name": student.name,
            "roll_no": student.roll_number,
        },
    )

    _audit(db, user, "student.enroll" if created else "student.update", "student", student.id)
    db.commit()
    db.refresh(student)

    return {
        "student": student_dict(student),
        "created": created,
        "embedding_indexed": vector_service.is_ready,
    }


@router.get("/api/students")
def list_students(
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
    department: str | None = Query(default=None, max_length=120),
):
    stmt = select(Student).order_by(Student.name)
    if user.role not in STAFF_ROLES:
        stmt = stmt.where(Student.user_id == user.id)
    elif department:
        stmt = stmt.where(Student.department == department)
    students = db.scalars(stmt).all()
    return {"students": [student_dict(s) for s in students], "total": len(students)}


@router.get("/api/students/me")
def my_student(user: User = Depends(get_current_user_row), db: Session = Depends(get_db)):
    return student_dict(_require_student(db, user.id))


@router.get("/api/students/me/face")
def my_face(user: User = Depends(get_current_user_row), db: Session = Depends(get_db)):
    """Return the caller's own enrollment photo as a data URL.

    Biometric originals stay server-side (and out of the browser cache) except
    for this explicit owner-only fetch, which the verification screen needs for
    the ArcFace comparison.
    """
    import base64

    student = _require_student(db, user.id)
    data = image_store.load(student.face_image_key)
    if data is None:
        raise HTTPException(status_code=404, detail="No enrollment photo on file.")
    return {"image_base64": "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")}


@router.delete("/api/students/{student_id}")
def delete_student(
    student_id: str,
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    if student.user_id != user.id and user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed to delete this profile.")

    image_store.delete(student.face_image_key)
    vector_service.delete(student.user_id)
    uid = student.user_id
    _audit(db, user, "student.delete", "student", student_id)
    db.delete(student)
    db.commit()
    return {"deleted": True, "uid": uid}


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
@router.post("/api/attendance")
def mark_attendance(
    payload: AttendanceCreate,
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
):
    target_uid = payload.student_uid or user.id
    if target_uid != user.id and user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Only staff can record attendance for others.")

    student = _require_student(db, target_uid)
    captured_at = to_naive_utc(payload.captured_at) or utcnow()

    session = None
    if payload.session_id is not None:
        session = db.get(ClassSession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Class session not found.")

    # Idempotency: one mark per student per session, else one per day per method.
    if session is not None:
        existing = db.scalar(
            select(Attendance).where(
                Attendance.student_id == student.id,
                Attendance.session_id == session.id,
            )
        )
    else:
        start, end = _day_bounds(captured_at)
        existing = db.scalar(
            select(Attendance).where(
                Attendance.student_id == student.id,
                Attendance.method == payload.method,
                Attendance.captured_at >= start,
                Attendance.captured_at < end,
            )
        )
    if existing is not None:
        return {"record": attendance_dict(existing), "duplicate": True}

    record = Attendance(
        student_id=student.id,
        session_id=session.id if session else None,
        captured_at=captured_at,
        method=payload.method,
        liveness_score=payload.liveness_score,
        distance=payload.distance,
        recorded_by=user.id,
    )
    db.add(record)
    _audit(db, user, "attendance.create", "attendance", None)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Another request committed the same mark between our check and insert
        # (the partial unique index is the real guard). Return the winner.
        if session is not None:
            again = db.scalar(
                select(Attendance).where(
                    Attendance.student_id == student.id,
                    Attendance.session_id == session.id,
                )
            )
        else:
            start, end = _day_bounds(captured_at)
            again = db.scalar(
                select(Attendance).where(
                    Attendance.student_id == student.id,
                    Attendance.method == payload.method,
                    Attendance.captured_at >= start,
                    Attendance.captured_at < end,
                )
            )
        if again is None:
            raise HTTPException(status_code=409, detail="Attendance already recorded.")
        return {"record": attendance_dict(again), "duplicate": True}

    db.refresh(record)
    return {"record": attendance_dict(record), "duplicate": False}


@router.get("/api/attendance")
def list_attendance(
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
    student_uid: str | None = Query(default=None, max_length=128),
    method: str | None = Query(default=None, max_length=30),
    session_id: int | None = None,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
):
    stmt = select(Attendance).join(Student).order_by(Attendance.captured_at.desc()).limit(limit)

    if user.role not in STAFF_ROLES:
        stmt = stmt.where(Student.user_id == user.id)
    elif student_uid:
        stmt = stmt.where(Student.user_id == student_uid)

    if method:
        stmt = stmt.where(Attendance.method == method)
    if session_id is not None:
        stmt = stmt.where(Attendance.session_id == session_id)
    if date_from:
        stmt = stmt.where(Attendance.captured_at >= (to_naive_utc(date_from) or utcnow()))
    if date_to:
        stmt = stmt.where(Attendance.captured_at <= (to_naive_utc(date_to) or utcnow()))

    rows = db.scalars(stmt).all()
    return {"records": [attendance_dict(r) for r in rows], "total": len(rows)}


@router.get("/api/attendance/summary")
def attendance_summary(
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
    days: int = Query(default=7, ge=1, le=90),
):
    since = utcnow() - timedelta(days=days)
    stmt = select(Attendance).where(Attendance.captured_at >= since)
    if user.role not in STAFF_ROLES:
        stmt = stmt.join(Student).where(Student.user_id == user.id)
    rows = db.scalars(stmt).all()

    buckets: dict[str, dict] = {}
    for offset in range(days):
        day = (utcnow() - timedelta(days=days - 1 - offset)).date().isoformat()
        buckets[day] = {"date": day, "total": 0, "byMethod": {}}

    by_method: dict[str, int] = {}
    for row in rows:
        day = as_utc(row.captured_at).date().isoformat() if row.captured_at else None
        if day in buckets:
            buckets[day]["total"] += 1
            buckets[day]["byMethod"][row.method] = buckets[day]["byMethod"].get(row.method, 0) + 1
        by_method[row.method] = by_method.get(row.method, 0) + 1

    return {
        "days": list(buckets.values()),
        "byMethod": by_method,
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
@router.get("/api/analytics/overview")
def analytics_overview(
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
):
    if user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff only.")

    today_start, today_end = _day_bounds(utcnow())
    week_ago = utcnow() - timedelta(days=7)

    students_total = db.scalar(select(func.count()).select_from(Student)) or 0
    attendance_today = db.scalar(
        select(func.count(func.distinct(Attendance.student_id))).where(
            Attendance.captured_at >= today_start,
            Attendance.captured_at < today_end,
        )
    ) or 0
    attendance_week = db.scalar(
        select(func.count()).select_from(Attendance).where(Attendance.captured_at >= week_ago)
    ) or 0

    method_rows = db.execute(
        select(Attendance.method, func.count()).where(Attendance.captured_at >= week_ago).group_by(Attendance.method)
    ).all()

    dept_rows = db.execute(
        select(Student.department, func.count(func.distinct(Attendance.student_id)))
        .join(Attendance, Attendance.student_id == Student.id)
        .where(Attendance.captured_at >= week_ago)
        .group_by(Student.department)
    ).all()

    cameras_total = db.scalar(select(func.count()).select_from(Camera)) or 0
    cameras_online = db.scalar(
        select(func.count()).select_from(Camera).where(Camera.status == "online")
    ) or 0

    upcoming = db.scalar(
        select(func.count()).select_from(ClassSession).where(ClassSession.starts_at >= utcnow())
    ) or 0

    return {
        "studentsTotal": students_total,
        "attendanceToday": attendance_today,
        "attendanceLast7Days": attendance_week,
        "byMethod": {method: count for method, count in method_rows},
        "byDepartment": [{"department": dept or "Unassigned", "students": count} for dept, count in dept_rows],
        "cameras": {"total": cameras_total, "online": cameras_online},
        "upcomingSessions": upcoming,
    }


# ---------------------------------------------------------------------------
# Class sessions
# ---------------------------------------------------------------------------
@router.post("/api/sessions")
def create_session(
    payload: SessionCreate,
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
):
    course = None
    if payload.course_code:
        course = db.scalar(select(Course).where(Course.code == payload.course_code))

    session = ClassSession(
        course_id=course.id if course else None,
        title=payload.title or (course.title if course else None),
        room=payload.room,
        teacher_id=user.id,
        starts_at=to_naive_utc(payload.starts_at) or utcnow(),
        ends_at=to_naive_utc(payload.ends_at),
        status=payload.status,
    )
    db.add(session)
    _audit(db, user, "session.create", "class_session", None)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "room": session.room,
        "startsAt": _iso(session.starts_at),
        "endsAt": _iso(session.ends_at),
        "status": session.status,
        "courseCode": course.code if course else None,
        "attendanceCount": 0,
    }


@router.get("/api/sessions")
def list_sessions(
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = db.scalars(select(ClassSession).order_by(ClassSession.starts_at.desc()).limit(limit)).all()
    counts = dict(
        db.execute(
            select(Attendance.session_id, func.count()).group_by(Attendance.session_id)
        ).all()
    )
    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "room": s.room,
                "startsAt": _iso(s.starts_at),
                "endsAt": _iso(s.ends_at),
                "status": s.status,
                "courseCode": s.course.code if s.course else None,
                "attendanceCount": counts.get(s.id, 0),
            }
            for s in rows
        ]
    }


# ---------------------------------------------------------------------------
# Leave requests
# ---------------------------------------------------------------------------
@router.post("/api/leave")
def create_leave(
    payload: LeaveCreate,
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
):
    student = _require_student(db, user.id)
    if payload.session_id is not None and db.get(ClassSession, payload.session_id) is None:
        raise HTTPException(status_code=404, detail="Class session not found.")
    leave = LeaveRequest(student_id=student.id, session_id=payload.session_id, reason=payload.reason)
    db.add(leave)
    _audit(db, user, "leave.create", "leave", None)
    db.commit()
    db.refresh(leave)
    return {"id": leave.id, "status": leave.status, "sessionId": leave.session_id}


@router.get("/api/leave")
def list_leave(
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
):
    stmt = select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    if user.role not in STAFF_ROLES:
        student = _require_student(db, user.id)
        stmt = stmt.where(LeaveRequest.student_id == student.id)
    rows = db.scalars(stmt).all()
    return {
        "requests": [
            {
                "id": r.id,
                "studentId": r.student_id,
                "sessionId": r.session_id,
                "reason": r.reason,
                "status": r.status,
                "createdAt": _iso(r.created_at),
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------
@router.post("/api/admin/backfill-embeddings")
def backfill_embeddings(
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    if not face_service.is_ready:
        raise HTTPException(status_code=503, detail="Face recognition model not loaded.")

    students = db.scalars(select(Student)).all()
    indexed, skipped = 0, 0
    for student in students:
        data = image_store.load(student.face_image_key)
        if not data:
            skipped += 1
            continue
        embedding = face_service.get_face_encoding(data)
        if embedding is None:
            skipped += 1
            continue
        vector_service.upsert(
            uid=student.user_id,
            embedding=embedding,
            payload={"uid": student.user_id, "name": student.name, "roll_no": student.roll_number},
        )
        indexed += 1

    _audit(db, user, "embeddings.backfill", "student", None)
    db.commit()
    return {"indexed": indexed, "skipped": skipped, "totalInIndex": vector_service.count()}
