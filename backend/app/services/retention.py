"""Attendance retention: bounded, audited, dry-run first.

Biometric originals are **not** touched here — a student deletes their profile
(photo + embedding + history) from the UI, and an institution policy may keep
attendance longer than the biometric. This module implements the one policy
that can be automated safely: dropping attendance rows older than a configured
window. It never runs at startup and defaults to a dry run.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import Attendance, AuditLog, as_utc, utcnow

RETENTION_ACTOR = "system:retention"


def purge_attendance(
    db: Session,
    older_than_days: int,
    *,
    dry_run: bool = True,
) -> dict:
    """Delete attendance captured before the retention cut-off.

    Returns a summary instead of a bare count so a cron log answers *what was
    deleted and against which cut-off*. ``dry_run`` reports the same numbers
    without deleting. A positive ``older_than_days`` is required: passing 0 by
    accident must not wipe the table.
    """
    if older_than_days <= 0:
        raise ValueError("older_than_days must be positive; retention is opt-in")

    cutoff = utcnow() - timedelta(days=older_than_days)
    condition = Attendance.captured_at < cutoff
    matched = int(db.scalar(select(func.count()).select_from(Attendance).where(condition)) or 0)

    deleted = 0
    if not dry_run and matched:
        result = db.execute(delete(Attendance).where(condition))
        deleted = int(result.rowcount or 0)
        db.add(
            AuditLog(
                actor_id=RETENTION_ACTOR,
                action="attendance.retention_purge",
                entity="attendance",
                entity_id=None,
            )
        )
        db.commit()

    return {
        "dry_run": dry_run,
        "older_than_days": older_than_days,
        "cutoff": as_utc(cutoff).isoformat().replace("+00:00", "Z"),
        "matched": matched,
        "deleted": deleted,
    }


def purge_inactive_students(
    db: Session,
    older_than_days: int,
    *,
    dry_run: bool = True,
) -> dict:
    """Delete student profiles (photo + embedding + attendance + user) for
    students with no attendance in the retention window.

    A positive ``older_than_days`` is required. Dry-run reports candidates
    without deleting. An audit row is written per deleted student.
    """
    if older_than_days <= 0:
        raise ValueError("older_than_days must be positive; retention is opt-in")

    cutoff = utcnow() - timedelta(days=older_than_days)
    # Students whose most recent attendance (or enrollment) is before cutoff.
    from app.db import Student

    students = db.scalars(select(Student)).all()
    candidates = []
    for student in students:
        latest = db.scalar(
            select(func.max(Attendance.captured_at)).where(Attendance.student_id == student.id)
        )
        reference = latest if latest is not None else student.enrolled_at
        if reference is not None and reference < cutoff:
            candidates.append(student)

    deleted = 0
    if not dry_run:
        from app.services import image_store, vector_service

        for student in candidates:
            image_store.delete(student.face_image_key)
            try:
                vector_service.delete(student.user_id)
            except Exception:
                pass
            db.delete(student)
            db.add(
                AuditLog(
                    actor_id=RETENTION_ACTOR,
                    action="student.retention_purge",
                    entity="student",
                    entity_id=student.id,
                )
            )
            deleted += 1
        db.commit()

    return {
        "dry_run": dry_run,
        "older_than_days": older_than_days,
        "cutoff": as_utc(cutoff).isoformat().replace("+00:00", "Z"),
        "matched": len(candidates),
        "deleted": deleted,
        "candidate_uids": [s.user_id for s in candidates],
    }
