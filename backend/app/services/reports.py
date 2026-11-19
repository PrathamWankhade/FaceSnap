"""CSV report builders shared by API routes and scheduled scripts.

Keeping the column layout in one place means the on-demand
``GET /api/reports/attendance`` export and the scheduled email report can
never drift apart.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from app.db import Attendance, as_utc

COLUMNS = [
    "attendance_id", "student_uid", "student_name", "roll_number", "department",
    "captured_at", "method", "session_id", "camera_id", "liveness_score",
    "distance", "recorded_by",
]


def _iso(value: datetime | None) -> str | None:
    dt = as_utc(value)
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def attendance_csv(records: list[Attendance]) -> str:
    """Render attendance rows as CSV text (header + one row per record)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for record in records:
        student = record.student
        writer.writerow([
            record.id,
            student.user_id if student else None,
            student.name if student else None,
            student.roll_number if student else None,
            student.department if student else None,
            _iso(record.captured_at),
            record.method,
            record.session_id,
            record.camera_id,
            record.liveness_score,
            record.distance,
            record.recorded_by,
        ])
    return buffer.getvalue()
