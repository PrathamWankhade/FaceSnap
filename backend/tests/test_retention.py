"""Retention purge: dry run, apply, audit trail, and the opt-in guard."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db import Attendance, AuditLog, Base, Student, User, utcnow
from app.services.retention import purge_attendance


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'retention.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id="u1", email="a@example.com", display_name="A", role="student"))
    db.flush()
    db.add(
        Student(
            id="s1",
            user_id="u1",
            name="A",
            roll_number="R1",
            department="CS",
            year="3",
            semester="5",
        )
    )
    db.flush()
    db.add_all(
        [
            Attendance(
                student_id="s1",
                method="individual_live",
                captured_at=utcnow() - timedelta(days=400),
            ),
            Attendance(
                student_id="s1",
                method="doorway_batch",
                captured_at=utcnow() - timedelta(days=10),
            ),
        ]
    )
    db.commit()
    return db


def test_dry_run_reports_but_does_not_delete(tmp_path):
    db = _session(tmp_path)
    summary = purge_attendance(db, older_than_days=365)

    assert summary["dry_run"] is True
    assert summary["matched"] == 1
    assert summary["deleted"] == 0
    assert summary["cutoff"].endswith("Z")
    assert db.scalar(select(func.count()).select_from(Attendance)) == 2
    assert db.scalar(select(func.count()).select_from(AuditLog)) == 0
    db.close()


def test_apply_deletes_only_the_old_rows_and_writes_an_audit_row(tmp_path):
    db = _session(tmp_path)
    summary = purge_attendance(db, older_than_days=365, dry_run=False)

    assert summary["matched"] == 1
    assert summary["deleted"] == 1
    remaining = db.scalars(select(Attendance)).all()
    assert len(remaining) == 1
    assert remaining[0].method == "doorway_batch"

    audit = db.scalar(select(AuditLog).where(AuditLog.action == "attendance.retention_purge"))
    assert audit is not None
    assert audit.actor_id == "system:retention"
    db.close()


def test_zero_or_negative_window_is_rejected(tmp_path):
    db = _session(tmp_path)
    with pytest.raises(ValueError):
        purge_attendance(db, older_than_days=0)
    with pytest.raises(ValueError):
        purge_attendance(db, older_than_days=-1)
    db.close()
