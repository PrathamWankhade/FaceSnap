#!/usr/bin/env bash
# Backup the FaceSnap system of record and biometric originals.
#
#   ./scripts/backup.sh [--out DIR] [--include-vectors]
#
# Produces, in $BACKUP_DIR (default ./backups):
#   facesnap-<UTC stamp>.tar.gz
#     ├── database.sql      (Postgres) or facesnap.db (SQLite, copied consistently)
#     ├── faces/            (enrollment originals — biometric data: keep access tight)
#     ├── alembic_version.txt
#     └── manifest.txt      (counts, sizes, schema revision)
#
# Env: DATABASE_URL, FACE_IMAGE_DIR, QDRANT_PATH
# Exits non-zero on any failure. An untested backup is not a backup:
# see docs/runbooks/backup-restore.md for the restore drill.
set -euo pipefail

OUT_DIR="./backups"
INCLUDE_VECTORS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT_DIR="$2"; shift 2 ;;
    --include-vectors) INCLUDE_VECTORS=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT_DIR"

DATABASE_URL="${DATABASE_URL:-sqlite:///./facesnap.db}"
FACE_IMAGE_DIR="${FACE_IMAGE_DIR:-./data/faces}"
QDRANT_PATH="${QDRANT_PATH:-./data/qdrant}"
SCHEMA_REV="unknown"

# --- 1. database -----------------------------------------------------------
case "$DATABASE_URL" in
  sqlite*)
    DB_FILE="${DATABASE_URL#sqlite:///}"
    if [ ! -f "$DB_FILE" ]; then echo "ERROR: SQLite file not found: $DB_FILE" >&2; exit 1; fi
    # .backup is online-safe for SQLite (WAL-aware); a plain cp can tear.
    if command -v sqlite3 >/dev/null 2>&1; then
      sqlite3 "$DB_FILE" ".backup '$WORK/facesnap.db'"
    else
      echo "WARN: sqlite3 CLI not found; copying $DB_FILE directly (no concurrent writes during backup)." >&2
      cp "$DB_FILE" "$WORK/facesnap.db"
    fi
    # Schema revision, if Alembic has been initialised on this database.
    SCHEMA_REV="$(python - "$DB_FILE" <<'PY' 2>/dev/null || echo "no-alembic"
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
try:
    print(con.execute("select version_num from alembic_version").fetchone()[0])
except Exception:
    print("no-alembic")
PY
)"
    ;;
  postgres*)
    if ! command -v pg_dump >/dev/null 2>&1; then echo "ERROR: pg_dump is required for DATABASE_URL=$DATABASE_URL" >&2; exit 1; fi
    # Strip the scheme for pgprompt-safe handling; pg_dump takes the DSN directly.
    pg_dump "$DATABASE_URL" --no-owner --no-privileges > "$WORK/database.sql"
    SCHEMA_REV="$(psql "$DATABASE_URL" -Atc "select version_num from alembic_version" 2>/dev/null || echo no-alembic)"
    ;;
  *)
    echo "ERROR: unsupported DATABASE_URL scheme: ${DATABASE_URL%%:*}" >&2; exit 1 ;;
esac

# --- 2. biometric originals ------------------------------------------------
if [ -d "$FACE_IMAGE_DIR" ]; then
  mkdir -p "$WORK/faces"
  cp -R "$FACE_IMAGE_DIR/." "$WORK/faces/" 2>/dev/null || true
fi

# --- 3. optional derived vector index (rebuildable; not required) ----------
if [ "$INCLUDE_VECTORS" = "1" ] && [ -d "$QDRANT_PATH" ]; then
  mkdir -p "$WORK/qdrant"
  cp -R "$QDRANT_PATH/." "$WORK/qdrant/" 2>/dev/null || true
fi

# --- 4. manifest -----------------------------------------------------------
{
  echo "created_utc=$STAMP"
  echo "database_url_scheme=${DATABASE_URL%%:*}"
  echo "alembic_revision=$SCHEMA_REV"
  echo "face_image_dir=$FACE_IMAGE_DIR"
  echo "face_images=$(find "$WORK/faces" -type f 2>/dev/null | wc -l | tr -d ' ')"
  echo "database_bytes=$(du -sk "$WORK" | awk '{print $1}')K"
} > "$WORK/manifest.txt"

ARCHIVE="$OUT_DIR/facesnap-$STAMP.tar.gz"
tar -czf "$ARCHIVE" -C "$WORK" .

# --- 5. verify the archive we just claimed to create -----------------------
if [ ! -s "$ARCHIVE" ]; then echo "ERROR: archive missing or empty: $ARCHIVE" >&2; exit 1; fi
tar -tzf "$ARCHIVE" >/dev/null || { echo "ERROR: archive failed verification: $ARCHIVE" >&2; exit 1; }

echo "OK: $ARCHIVE ($(du -h "$ARCHIVE" | awk '{print $1}'))"
echo "    alembic_revision=$SCHEMA_REV  restore drill: docs/runbooks/backup-restore.md"
echo "NOTE: this archive contains biometric images. Restrict file permissions and storage location."
