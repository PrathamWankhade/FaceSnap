# Runbook: backup & restore

Backups exist for two unrebuildable things: **the SQL system of record** and **the enrollment
photos** (`FACE_IMAGE_DIR`). The Qdrant index is *not* required — it is rebuilt from SQL with
`POST /api/admin/backfill-embeddings` ([`../caching.md`](../caching.md)).

NFR-O4: a backup that has never been restored is not a backup. **Run the drill quarterly** and
after any schema change.

## Take a backup

```bash
cd backend  # or the deploy root, with env vars pointing at production
../scripts/backup.sh --out ./backups
# --include-vectors  also snapshots Qdrant (optional; saves a rebuild only)
```

Produces `backups/facesnap-<UTC>.tar.gz` containing:

| Entry | Source |
|-------|--------|
| `database.sql` or `facesnap.db` | `pg_dump` (online) or SQLite `.backup` (WAL-aware) |
| `faces/` | enrollment photos |
| `alembic_version.txt` → in `manifest.txt` | schema revision at backup time |
| `manifest.txt` | timestamp, counts, schema revision |

The script **fails non-zero** if the dump or archive is empty or unreadable.

### Schedule

Daily automated + before every migration-bearing deploy (see [`deploy.md`](deploy.md)).
Retention: keep ≥ 14 daily, ≥ 8 weekly. The backup directory holds **biometric data** —
restrict permissions (`chmod 700`) and store it in the same jurisdiction as production.

> No scheduler is provisioned in this repo (no IaC yet — [`../hosting.md`](../hosting.md)).
> The job must be wired by whoever owns the host, and its success must be alerted on
> ([`../monitoring.md`](../monitoring.md) § alerting).

## Restore (the drill)

Always restore into a **clean** target — never over the live database.

```bash
# 1. dry run: inspect what the archive actually contains
./scripts/restore.sh backups/facesnap-20261023T101500Z.tar.gz --dry-run

# 2. restore into an empty location
./scripts/restore.sh backups/facesnap-20261023T101500Z.tar.gz \
  --db-url sqlite:///./restored.db \
  --faces ./restored-faces
```

Then verify, in order:

1. `python -m alembic current` → revision matches `manifest.txt`.
2. Start the app against the restored DB with **auth enabled**.
3. `GET /api/health` → `ok: true` and counts match expectations (`students_in_db`,
   `attendance_rows` non-zero and equal to the pre-incident numbers).
4. Spot-check: `/api/students` shows the expected people; one attendance row is readable.
5. Rebuild the derived index: `POST /api/admin/backfill-embeddings` (admin), then confirm
   `embeddings_indexed == students_in_db`.
6. Exercise the app: enroll, verify, attendance write.

**The drill is not passed until step 3–6 all succeed.** Record date, archive, elapsed time and
any surprise in the repo (or your ops log).

## Restore during an incident

Order: **stop writes → restore → point the app at it → rebuild vectors → verify → resume.**
If the schema moved on after the backup, run `alembic upgrade head` on the restored DB before
starting the new code ([`migrate.md`](migrate.md)).

## Known gaps

- Restore is manual (no automated restore verification, no cross-region copy).
- No point-in-time recovery on SQLite; for Postgres, `pg_dump` is a snapshot — PITR requires
  WAL archiving configured on the host, which is not provisioned here.
- Photos and the database are backed up in one archive, so the two are consistent with each other
  but are not independently encrypted. Add at-rest encryption where the host allows it before
  storing real student data.
