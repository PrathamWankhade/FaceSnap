"""Idempotent student upsert from a CSV (HR/SIS sync).

Usage:
    python scripts/sync_students.py --csv students.csv [--dry-run]

CSV columns (header required):
    uid (or user_uid), name, roll_number, department, year, semester,
    consent_version (optional)

Existing students are updated in place (matched by roll_number, then uid);
new ones are created with a fresh profile row. The script never deletes rows
and never touches biometric data; it only upserts profile fields. Dry-run
prints the planned changes without writing.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, Student, User, utcnow


def _read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("CSV has no header row.")
        return [row for row in reader]


def _find_existing(db, row: dict) -> Student | None:
    roll = (row.get("roll_number") or "").strip()
    if roll:
        found = db.scalar(__import__("sqlalchemy").select(Student).where(Student.roll_number == roll))
        if found is not None:
            return found
    uid = (row.get("uid") or row.get("user_uid") or "").strip()
    if uid:
        return db.scalar(__import__("sqlalchemy").select(Student).where(Student.user_id == uid))
    return None


def sync(rows: list[dict], dry_run: bool = False) -> dict:
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    with SessionLocal() as db:
        for index, row in enumerate(rows, start=2):
            try:
                name = (row.get("name") or "").strip()
                roll = (row.get("roll_number") or "").strip()
                department = (row.get("department") or "").strip()
                year = (row.get("year") or "").strip()
                semester = (row.get("semester") or "").strip()
                uid = (row.get("uid") or row.get("user_uid") or "").strip()
                if not name or not roll:
                    skipped += 1
                    continue

                existing = _find_existing(db, row)
                if existing is None:
                    if not uid:
                        errors.append(f"row {index}: new student needs a uid")
                        skipped += 1
                        continue
                    # ensure user row exists
                    user = db.get(User, uid)
                    if user is None:
                        user = User(id=uid, email=None, display_name=name, role="student")
                        db.add(user)
                        db.flush()
                    student = Student(
                        id=__import__("uuid").uuid4().__str__(),
                        user_id=uid,
                        name=name,
                        roll_number=roll,
                        department=department,
                        year=year,
                        semester=semester,
                    )
                    cv = (row.get("consent_version") or "").strip()
                    if cv:
                        student.consent_version = cv
                        student.consent_at = utcnow()
                    if dry_run:
                        print(f"[dry-run] CREATE {roll} ({name})")
                    else:
                        db.add(student)
                        db.flush()
                    created += 1
                else:
                    if dry_run:
                        print(f"[dry-run] UPDATE {roll} ({existing.name} -> {name})")
                    else:
                        existing.name = name
                        existing.roll_number = roll
                        existing.department = department
                        existing.year = year
                        existing.semester = semester
                        cv = (row.get("consent_version") or "").strip()
                        if cv and cv != existing.consent_version:
                            existing.consent_version = cv
                            existing.consent_at = utcnow()
                        db.flush()
                    updated += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"row {index}: {exc}")
                skipped += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync students from a CSV into FaceSnap.")
    parser.add_argument("--csv", required=True, help="Path to the CSV file.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing.")
    args = parser.parse_args()

    rows = _read_csv(args.csv)
    result = sync(rows, dry_run=args.dry_run)
    print(result)
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())