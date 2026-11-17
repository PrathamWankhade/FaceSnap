"""Postgres backup helper (pg_dump wrapper).

Usage:
    python scripts/backup_postgres.py --out backups/facesnap_$(date).sql.gz

Requires pg_dump on PATH and DATABASE_URL pointing at Postgres.
"""
from __future__ import annotations

import argparse
import gzip
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import DATABASE_URL


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up a Postgres FaceSnap database.")
    parser.add_argument("--out", help="Output file path (default: backups/facesnap_<ts>.sql.gz)")
    args = parser.parse_args()

    if not DATABASE_URL.startswith("postgres"):
        print("DATABASE_URL is not a Postgres DSN; this script is Postgres-only.", file=sys.stderr)
        return 2
    if shutil.which("pg_dump") is None:
        print("pg_dump not found on PATH. Install postgresql-client.", file=sys.stderr)
        return 2

    out = args.out or f"backups/facesnap_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sql.gz"
    Path(out).parent.mkdir(parents=True, exist_ok=True)

    # Convert SQLAlchemy DSN to pg_dump connection string.
    dsn = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")

    with open(out, "wb") as fh:
        proc = subprocess.Popen(["pg_dump", dsn], stdout=subprocess.PIPE)
        with gzip.GzipFile(fileobj=fh, mode="wb") as gz:
            assert proc.stdout is not None
            shutil.copyfileobj(proc.stdout, gz)
        rc = proc.wait()
    if rc != 0:
        print(f"pg_dump failed with exit code {rc}", file=sys.stderr)
        return rc
    print(f"Backup written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())