# Runbook: deploy

Scope: moving a FaceSnap backend/frontend from the currently running version to a new one.
Works for the compose stack in this repo; the same ordering applies on any host.

## Preconditions

- [ ] CI green on the commit you are deploying.
- [ ] You have a **fresh backup** (see [`backup-restore.md`](backup-restore.md)) taken *before* the
      schema changes, and you know how to restore it.
- [ ] Migration reviewed by hand: `python -m alembic check` (model ↔ migration diff) and the
      migration tested on a **copy** of production data, not just an empty database.
- [ ] Rollback target known: the previous image/tag + the matching `downgrade` revision.

## Steps

1. **Announce** (if anyone else is using it). Note the time and the current version.
2. **Backup** — `scripts/backup.sh` (DB dump + `FACE_IMAGE_DIR` tar). Verify the archive is non-empty.
3. **Migrate first, then start new code** (expand/contract):
   ```bash
   cd backend && python -m alembic upgrade head
   python -m alembic current        # must print the new revision
   ```
4. **Start the new code.** Compose: `docker compose up -d --build backend frontend`.
   Never deploy code that predates its own migration.
5. **Verify**
   - `GET /api/health/live` → `200`
   - `GET /api/health` → `ok: true`, `database_ready: true`, expected `students_in_db` /
     `attendance_rows` (**a count of 0 here means you booted against the wrong database — stop**)
   - frontend loads, sign-in works, `/api/me` returns the right role
   - backend logs are JSON with `request_id`s and **no stack traces**
   - `GET /api/metrics` is being scraped (if you have a collector)
6. **Smoke test the risky path** the change touched (enroll → verify → attendance row appears once).
7. **Watch** error rate and 401/403 spikes for 15 minutes ([`../monitoring.md`](../monitoring.md)).

## If anything fails

Go to [`rollback.md`](rollback.md) immediately — do not debug in place while users are failing.
Time-to-rollback should be measured in minutes; root cause can wait.

## Checklist for a *migration-bearing* deploy

- [ ] Migration has an `upgrade()` **and** a reviewed `downgrade()`
- [ ] Destructive operations are called out in the migration docstring with a data-loss warning
- [ ] `uq_attendance_daily` (partial unique index) still present after upgrade
- [ ] Old code still runs against the new schema (expand step) — required for zero-downtime
