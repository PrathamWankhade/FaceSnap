#!/usr/bin/env python
"""Consistent SQLite backup (and restore) for FaceSnap.

    python scripts/backup_db.py --out backups/facesnap-2026-11-17.db
    python scripts/backup_db.py --restore backups/facesnap-2026-11-17.db --out ./facesnap.db

The default source is ``DATABASE_URL`` when it points at SQLite. Postgres
deployments must use ``pg_dump``/``pg_restore``; this script refuses rather than
producing a file that looks like a backup and is not one.

Stop the API (or accept a hot copy via SQLite's online backup API) before
restoring over the live database.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import DATABASE_URL  # noqa: E402
from app.services.backup import sqlite_backup, sqlite_restore  # noqa: E402


def _sqlite_path(url: str) -> Path | None:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    raw = url[len(prefix):]
    return Path(raw).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--database", help="source SQLite path (default: DATABASE_URL)")
    parser.add_argument("--out", required=True, help="backup path (or restore target)")
    parser.add_argument(
        "--restore",
        metavar="BACKUP",
        help="restore this backup into --out instead of creating a backup",
    )
    args = parser.parse_args(argv)

    source = Path(args.database).resolve() if args.database else _sqlite_path(DATABASE_URL)
    if source is None:
        print(
            "DATABASE_URL is not SQLite. Use pg_dump/pg_restore for Postgres; "
            "see docs/runbooks/backup-restore.md.",
            file=sys.stderr,
        )
        return 2

    target = Path(args.out).resolve()
    try:
        if args.restore:
            sqlite_restore(Path(args.restore).resolve(), target)
            print(f"Restored {Path(args.restore).resolve()} -> {target}")
            print(f"sha256 {_sha256(target)}")
            return 0
        sqlite_backup(source, target)
    except (OSError, FileNotFoundError) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"Backup {source} -> {target}")
    print(f"sha256 {_sha256(target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
