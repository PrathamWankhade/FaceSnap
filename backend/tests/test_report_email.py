"""Shared attendance CSV builder + scheduled email report script."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Attendance, Base, Student, User, engine, utcnow
from app.services.reports import attendance_csv


@pytest.fixture(autouse=True)
def _schema():
    """The script reads the app DB, so it needs the schema like other suites."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "email_report.py"
    spec = importlib.util.spec_from_file_location("email_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'report.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id="u1", email="a@example.com", display_name="A", role="student"))
    db.flush()
    db.add(
        Student(
            id="s1",
            user_id="u1",
            name="Ada Lovelace",
            roll_number="R1",
            department="CS",
            year="3",
            semester="5",
        )
    )
    db.flush()
    db.add(
        Attendance(
            student_id="s1",
            method="individual_live",
            captured_at=utcnow(),
            distance=0.31,
            liveness_score=0.9,
        )
    )
    db.commit()
    return db


def test_attendance_csv_has_header_and_row(tmp_path):
    db = _db(tmp_path)
    rows = db.scalars(select(Attendance)).all()
    text = attendance_csv(rows)
    lines = text.strip().splitlines()
    assert lines[0].startswith("attendance_id,student_uid,student_name")
    assert len(lines) == 2
    assert "Ada Lovelace" in lines[1]
    db.close()


def test_email_report_dry_run_prints_csv(capsys):
    module = _load_script()
    rc = module.main(["--days", "7"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "attendance_id" in captured.out
    assert "Dry run" in captured.err


def test_email_report_apply_requires_recipient(monkeypatch):
    module = _load_script()
    monkeypatch.setattr("app.config.REPORT_EMAIL_TO", "")
    monkeypatch.setattr("app.config.SMTP_HOST", "")
    assert module.main(["--days", "7", "--apply"]) == 2


def test_email_report_apply_sends_csv_attachment(monkeypatch):
    module = _load_script()
    sent = []

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent.append(msg)

    monkeypatch.setitem(sys.modules, "smtplib", types.SimpleNamespace(SMTP=_FakeSMTP))
    monkeypatch.setattr("app.config.REPORT_EMAIL_TO", "ops@example.edu")
    monkeypatch.setattr("app.config.SMTP_HOST", "smtp.example.edu")
    monkeypatch.setattr("app.config.SMTP_USER", "")
    monkeypatch.setattr("app.config.SMTP_PASSWORD", "")

    rc = module.main(["--days", "7", "--apply"])
    assert rc == 0
    assert len(sent) == 1
    attachments = list(sent[0].iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename().endswith(".csv")
    payload = attachments[0].get_payload(decode=True).decode("utf-8")
    assert payload.startswith("attendance_id,")


def test_email_report_rejects_non_positive_days():
    module = _load_script()
    assert module.main(["--days", "0"]) == 2
