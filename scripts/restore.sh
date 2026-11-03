#!/usr/bin/env bash
# Restore a FaceSnap backup created by scripts/backup.sh into a clean environment.
#
#   ./scripts/restore.sh <archive.tar.gz> [--db-url URL] [--faces DIR] [--dry-run]
#
# Use against an EMPTY database. This is the restore half of the backup drill in
# docs/runbooks/backup-restore.md — run it regularly; an untested backup is not a backup.
set -euo pipefail

ARCHIVE="${1:-}"
[ -n "$ARCHIVE" ] || { echo "usage: $0 <archive.tar.gz> [--db-url URL] [--faces DIR] [--dry-run]" >&2; exit 2; }
[ -f "$ARCHIVE" ] || { echo "ERROR: no such archive: $ARCHIVE" >&2; exit 1; }
shift

DB_URL="${DATABASE_URL:-sqlite:///./facesnap.db}"
FACES="${FACE_IMAGE_DIR:-./data/faces}"
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --db-url) DB_URL="$2"; shift 2 ;;
    --faces) FACES="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

tar -xzf "$ARCHIVE" -C "$WORK"
echo "Archive contents:"
cat "$WORK/manifest.txt" 2>/dev/null || true
echo "------------------"

if [ "$DRY" = "1" ]; then
  echo "DRY RUN: nothing restored. Would restore DB into ${DB_URL%%:*} and faces into $FACES"
  exit 0
fi

# --- database --------------------------------------------------------------
case "$DB_URL" in
  sqlite*)
    DB_FILE="${DB_URL#sqlite:///}"
    if [ -f "$DB_FILE" ]; then
      echo "ERROR: $DB_FILE already exists. Restore into a clean location, then swap." >&2
      exit 1
    fi
    mkdir -p "$(dirname "$DB_FILE")"
    cp "$WORK/facesnap.db" "$DB_FILE"
    echo "restored SQLite -> $DB_FILE"
    ;;
  postgres*)
    command -v psql >/dev/null 2>&1 || { echo "ERROR: psql required" >&2; exit 1; }
    # Restore into a fresh/empty DB; psql fails loudly on pre-existing objects.
    psql "$DB_URL" -v ON_ERROR_STOP=1 --quiet < "$WORK/database.sql"
    echo "restored Postgres -> ${DB_URL%%://*}"
    ;;
  *) echo "ERROR: unsupported scheme" >&2; exit 1 ;;
esac

# --- biometric originals ---------------------------------------------------
if [ -d "$WORK/faces" ]; then
  mkdir -p "$FACES"
  cp -R "$WORK/faces/." "$FACES/"
  echo "restored $(find "$FACES" -type f | wc -l | tr -d ' ') face images -> $FACES"
fi

echo
echo "Post-restore verification (all must pass before serving traffic):"
echo "  1. python -m alembic current      # revision matches pre-incident state"
echo "  2. uvicorn app.main:app ...       # then:"
echo "  3. curl -fsS localhost:8000/api/health | grep -o '\"ok\":true'"
echo "  4. compare students_in_db / attendance_rows against manifest.txt expectations"
echo "  5. rebuild derived index: POST /api/admin/backfill-embeddings (admin)"
