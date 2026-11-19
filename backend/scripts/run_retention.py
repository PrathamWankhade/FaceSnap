"""Run the retention purge using environment configuration.

Intended for cron / a scheduler:

    RETENTION_DAYS=90 python scripts/run_retention.py            # dry run
    RETENTION_DAYS=90 python scripts/run_retention.py --apply    # apply

Defaults to a dry run so a misconfigured cron never deletes data silently.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Scheduled retention purge.")
    parser.add_argument("--apply", action="store_true", help="apply the purge (default: dry run)")
    args = parser.parse_args()

    days = os.getenv("RETENTION_DAYS", "90")
    try:
        int(days)
    except ValueError:
        print(f"RETENTION_DAYS must be an integer, got {days!r}", file=sys.stderr)
        return 2

    cmd = [sys.executable, str(Path(__file__).with_name("purge_retention.py")), "--days", days]
    if args.apply:
        cmd.append("--apply")
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())