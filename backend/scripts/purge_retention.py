#!/usr/bin/env python
"""Delete attendance older than the retention window (dry run by default).

    python scripts/purge_retention.py --days 365            # report only
    python scripts/purge_retention.py --days 365 --apply    # delete + audit

Days default to ``ATTENDANCE_RETENTION_DAYS`` (0 means "no policy configured",
which is rejected rather than interpreted as "delete everything"). The run is
recorded in ``audit_log`` with actor ``system:retention`` when ``--apply`` is
used. Biometric originals are out of scope: a student deletes those from their
profile, and an institution retention policy for photos needs its own decision.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ATTENDANCE_RETENTION_DAYS  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services.retention import purge_attendance  # noqa: E402


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
    args = parser.parse_args(argv)

    if args.days <= 0:
        print(
            "No retention window configured. Pass --days N (N > 0) or set "
            "ATTENDANCE_RETENTION_DAYS. Refusing to guess.",
            file=sys.stderr,
        )
        return 2

    try:
        with SessionLocal() as db:
            summary = purge_attendance(db, args.days, dry_run=not args.apply)
    except Exception as exc:  # noqa: BLE001 - CLI reports, does not traceback
        print(f"Retention purge failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["dry_run"]:
        print("\nDry run: nothing deleted. Re-run with --apply to delete.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
