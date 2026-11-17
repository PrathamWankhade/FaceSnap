"""Relational API: enrollment, attendance, sessions, analytics.

All writes go through FastAPI so the database stays the single source of truth
(the browser no longer writes attendance directly).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user_row, require_roles
from app.config import CONSENT_VERSION, DUPLICATE_FACE_DISTANCE, MODEL_VERSION
from app.db import (
    Attendance,
    AuditLog,
    Camera,
    ClassSession,
    Course,
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
    # Which consent notice the student accepted. Must equal the server's
    # current CONSENT_VERSION; a stale or missing acknowledgement is rejected.
    consent_version: str | None = Field(default=None, max_length=30)


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
        "consentVersion": student.consent_version,
        "modelVersion": student.model_version,
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
# Consent
# ---------------------------------------------------------------------------
CONSENT_SUMMARY = (
    "FaceSnap stores one enrollment photo and a derived face embedding to verify "
    "attendance. The photo is stored outside the relational database and the "
    "embedding can be rebuilt. Attendance records contain the method, timestamp, "
    "match distance and liveness score. You can delete your profile, photo, "
    "embedding and attendance history at any time from the student profile."
)


@router.get("/api/consent")
def consent_notice():
    """Public consent notice the register page must acknowledge.

    Enrollment rejects a row without the current version, so the browser can
    never silently enroll someone under an outdated notice.
    """
    return {
        "version": CONSENT_VERSION,
        "summary": CONSENT_SUMMARY,
        "policy": "docs/consent.md",
        "withdrawal": "Deleting the profile removes the photo, embedding and attendance history.",
    }


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

    if payload.consent_version != CONSENT_VERSION:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Consent acknowledgement is required and must match the current notice.",
                "required_consent_version": CONSENT_VERSION,
            },
        )

    try:
        image_bytes = image_store.decode_data_url(payload.image_base64)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # One detection pass: quality gates and the embedding come from the same
    # inference instead of decoding and detecting twice.
    assessment = face_service.assess_enrollment(image_bytes)
    if not assessment.get("ok"):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Enrollment photo rejected.",
                "reasons": assessment.get("reasons", []),
                "metrics": assessment.get("metrics", {}),
                "face_count": assessment.get("face_count", 0),
            },
        )
    embedding = assessment.get("embedding")
    if embedding is None:  # pragma: no cover - assess_enrollment sets a reason
        raise HTTPException(status_code=422, detail="Could not extract a face embedding.")

    # Duplicate-enrollment guard: the same face may not hold two identities.
    # Requires the vector index; when it is offline the response says so rather
    # than pretending a check happened.
    duplicate_checked = False
    search = getattr(vector_service, "search", None)
    if vector_service.is_ready and callable(search):
        duplicate_checked = True
        try:
            matches = search(
                embedding,
                limit=5,
                score_threshold=1.0 - DUPLICATE_FACE_DISTANCE,
            )
        except Exception:  # noqa: BLE001 - index errors must not block enrollment
            matches = []
            duplicate_checked = False
        for match in matches:
            if (
                match.get("uid") != target_uid
                and float(match.get("distance", 1.0)) <= DUPLICATE_FACE_DISTANCE
            ):
                _audit(db, user, "student.enroll.blocked_duplicate", "student", None)
                db.commit()
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "This face is already enrolled under another account. "
                                   "Contact staff if this is a mistake."
                    },
                )

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

    # Record consent with the version that was actually accepted. Re-enrolling
    # after a notice bump records the new version and timestamp.
    if student.consent_version != CONSENT_VERSION:
        student.consent_version = CONSENT_VERSION
        student.consent_at = utcnow()

    # Record which model produced this embedding so a future model swap can
    # identify rows that need re-enrollment/backfill.
    student.model_version = MODEL_VERSION

    student.face_image_key = image_store.save(student.id, payload.image_base64)
    db.flush()

    vector_service.upsert(
        uid=target_uid,
        embedding=embedding,
        payload={
            "uid": target_uid,
            "name": student.name,
            "roll_no": student.roll_number,
            "model_version": MODEL_VERSION,
        },
    )

    _audit(db, user, "student.enroll" if created else "student.update", "student", student.id)
    db.commit()
    db.refresh(student)

    return {
        "student": student_dict(student),
        "created": created,
        "embedding_indexed": vector_service.is_ready,
        "duplicate_checked": duplicate_checked,
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


@router.get("/api/students/{student_id}/export")
def export_student_data(
    student_id: str,
    user: User = Depends(get_current_user_row),
    db: Session = Depends(get_db),
):
    """Machine-readable copy of one student's data (access/portability).

    Owner or staff only. The enrollment photo is *not* inlined here — the owner
    can fetch it from ``/api/students/me/face`` — so an export file does not
    silently become a biometric archive. The export itself is audited.
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    if student.user_id != user.id and user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed to export this profile.")

    records = db.scalars(
        select(Attendance)
        .where(Attendance.student_id == student.id)
        .order_by(Attendance.captured_at)
    ).all()
    _audit(db, user, "student.export", "student", student.id)
    db.commit()

    return {
        "schema_version": 1,
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "profile": student_dict(student),
        "consent": {
            "version": student.consent_version,
            "accepted_at": _iso(student.consent_at),
        },
        "attendance": [attendance_dict(record) for record in records],
        "biometric": {
            "face_image_included": False,
            "model_version": student.model_version,
            "note": "Enrollment photo is available to the owner at /api/students/me/face.",
        },
    }


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
# Analytics trends
# ---------------------------------------------------------------------------
@router.get("/api/analytics/trends")
def analytics_trends(
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    group: str = Query(default="day", pattern="^(day|week|month)$"),
    days: int = Query(default=30, ge=1, le=365),
    department: str | None = Query(default=None, max_length=120),
):
    since = utcnow() - timedelta(days=days)
    stmt = select(Attendance).where(Attendance.captured_at >= since)
    if department:
        stmt = stmt.join(Student).where(Student.department == department)
    rows = db.scalars(stmt).all()

    buckets: dict[str, dict] = {}
    for row in rows:
        dt = as_utc(row.captured_at)
        if dt is None:
            continue
        if group == "day":
            key = dt.date().isoformat()
        elif group == "week":
            key = dt.date().replace(day=dt.date().day - dt.weekday()).isoformat()
        else:
            key = dt.strftime("%Y-%m")
        if key not in buckets:
            buckets[key] = {"period": key, "total": 0, "byMethod": {}}
        buckets[key]["total"] += 1
        buckets[key]["byMethod"][row.method] = buckets[key]["byMethod"].get(row.method, 0) + 1

    series = sorted(buckets.values(), key=lambda b: b["period"])
    return {"group": group, "days": days, "series": series, "total": len(rows)}


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
# Reports
# ---------------------------------------------------------------------------
@router.get("/api/reports/attendance")
def attendance_report(
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    student_uid: str | None = Query(default=None, max_length=128),
    method: str | None = Query(default=None, max_length=30),
    session_id: int | None = None,
    department: str | None = Query(default=None, max_length=120),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=5000, ge=1, le=50000),
):
    stmt = select(Attendance).join(Student).order_by(Attendance.captured_at.desc()).limit(limit)
    if student_uid:
        stmt = stmt.where(Student.user_id == student_uid)
    if method:
        stmt = stmt.where(Attendance.method == method)
    if session_id is not None:
        stmt = stmt.where(Attendance.session_id == session_id)
    if department:
        stmt = stmt.where(Student.department == department)
    if date_from:
        stmt = stmt.where(Attendance.captured_at >= (to_naive_utc(date_from) or utcnow()))
    if date_to:
        stmt = stmt.where(Attendance.captured_at <= (to_naive_utc(date_to) or utcnow()))

    rows = db.scalars(stmt).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "attendance_id", "student_uid", "student_name", "roll_number", "department",
        "captured_at", "method", "session_id", "camera_id", "liveness_score",
        "distance", "recorded_by",
    ])
    for record in rows:
        student = record.student
        writer.writerow([
            record.id,
            student.user_id,
            student.name,
            student.roll_number,
            student.department,
            _iso(record.captured_at),
            record.method,
            record.session_id,
            record.camera_id,
            record.liveness_score,
            record.distance,
            record.recorded_by,
        ])

    _audit(db, user, "report.attendance", "attendance", None)
    db.commit()

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="attendance_report.csv"'},
    )


# ---------------------------------------------------------------------------
# Cameras (registry)
# ---------------------------------------------------------------------------
class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    stream_url: str | None = Field(default=None, max_length=500)


@router.get("/api/cameras")
def list_cameras(user: User = Depends(get_current_user_row), db: Session = Depends(get_db)):
    rows = db.scalars(select(Camera).order_by(Camera.id)).all()
    return {
        "cameras": [
            {
                "id": c.id,
                "name": c.name,
                "location": c.location,
                "streamUrl": c.stream_url,
                "status": c.status,
                "createdAt": _iso(c.created_at),
            }
            for c in rows
        ]
    }


@router.post("/api/cameras")
def create_camera(
    payload: CameraCreate,
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
):
    cam = Camera(name=payload.name, location=payload.location, stream_url=payload.stream_url, status="offline")
    db.add(cam)
    _audit(db, user, "camera.create", "camera", None)
    db.commit()
    db.refresh(cam)
    return {"id": cam.id, "name": cam.name, "status": cam.status}


@router.delete("/api/cameras/{camera_id}")
def delete_camera(
    camera_id: int,
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
):
    cam = db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    _audit(db, user, "camera.delete", "camera", camera_id)
    db.delete(cam)
    db.commit()
    return {"deleted": True, "id": camera_id}
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
            payload={"uid": student.user_id, "name": student.name, "roll_no": student.roll_number, "model_version": MODEL_VERSION},
        )
        student.model_version = MODEL_VERSION
        indexed += 1

    _audit(db, user, "embeddings.backfill", "student", None)
    db.commit()
    return {"indexed": indexed, "skipped": skipped, "totalInIndex": vector_service.count()}
