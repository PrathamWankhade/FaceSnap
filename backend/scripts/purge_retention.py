#!/usr/bin/env python
"""Delete attendance older than the retention window (dry run by default).

    python scripts/purge_retention.py --days 365            # report only
    python scripts/purge_retention.py --days 365 --apply    # delete + audit
    python scripts/purge_retention.py --students --student-days 365 --apply

Days default to ``ATTENDANCE_RETENTION_DAYS`` (0 means "no policy configured",
which is rejected rather than interpreted as "delete everything"). The run is
recorded in ``audit_log`` with actor ``system:retention`` when ``--apply`` is
used.

``--students`` additionally purges *inactive* student profiles (photo +
embedding + attendance + user row) whose most recent activity is older than
``--student-days`` (default ``STUDENT_RETENTION_DAYS``). It is opt-in, requires
a positive window, and is audited per deleted student.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ATTENDANCE_RETENTION_DAYS  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services.retention import purge_attendance, purge_inactive_students  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=ATTENDANCE_RETENTION_DAYS,
        help="retention window in days (default: ATTENDANCE_RETENTION_DAYS)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete; without this flag the script only reports",
    )
    parser.add_argument(
        "--students",
        action="store_true",
        help="also purge inactive student profiles (biometric expiry)",
    )
    parser.add_argument(
        "--student-days",
        type=int,
        default=365,
        help="inactive-student window in days (default: 365)",
    )
    args = parser.parse_args(argv)

    if args.days <= 0 and not args.students:
        print(
            "No retention window configured. Pass --days N (N > 0) or set "
            "ATTENDANCE_RETENTION_DAYS. Refusing to guess.",
            file=sys.stderr,
        )
        return 2

    summaries: list[dict] = []
    try:
        with SessionLocal() as db:
            if args.days > 0:
                summaries.append(
                    purge_attendance(db, args.days, dry_run=not args.apply)
                )
            if args.students:
                summaries.append(
                    purge_inactive_students(
                        db, args.student_days, dry_run=not args.apply
                    )
                )
    except Exception as exc:  # noqa: BLE001 - CLI reports, does not traceback
        print(f"Retention purge failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summaries, indent=2, sort_keys=True))
    if any(s.get("dry_run") for s in summaries):
        print("\nDry run: nothing deleted. Re-run with --apply to delete.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
