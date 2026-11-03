# Runbook: migrate

Schema changes are versioned with Alembic ([`../decisions/0005`](../decisions/0005-alembic-migrations.md)).
`alembic upgrade head` is the **only** supported way to change a shared database.

```bash
cd backend
python -m alembic current        # what revision is this DB at?
python -m alembic heads          # what is the newest revision?
python -m alembic upgrade head   # apply
python -m alembic history        # the chain
```

## Authoring a change

```bash
# 1. edit models in app/db.py (or a new model module)
python -m alembic revision --autogenerate -m "describe the change"
# 2. READ THE GENERATED FILE. Autogenerate misses:
#      - partial indexes (our uq_attendance_daily)
#      - server defaults / ondelete behaviour
#      - anything it cannot see (enums, triggers)
# 3. write downgrade() explicitly; mark destructive ones loudly in the docstring
python -m alembic upgrade head
python -m alembic downgrade -1 && python -m alembic upgrade head   # both directions
```

Rules:
- **Model change + migration + test land in the same commit.**
- Test against a **fresh** database *and* an existing one; `create_all`-era databases must be
  stamped once (`python -m alembic stamp head`) before their first upgrade — see the note below.
- Never edit a revision that has been pushed; add a new one.
- CI runs `upgrade head` on an empty database and fails if the models and migrations disagree.

## Applying in an environment

- **`AUTO_MIGRATE=true` (default)** — the app applies migrations during startup before it serves
  traffic. Simple and safe for one instance; **not** safe to run concurrently from N replicas.
- **`AUTO_MIGRATE=false`** — run this runbook as an explicit deploy step (recommended for
  multi-replica deployments), then start the new code. See [`deploy.md`](deploy.md).

## Existing databases created before Alembic was added

The first migration is a *baseline* (it creates the current schema). If a database already has
those tables — e.g. a dev `facesnap.db` built by `create_all()` — the upgrade will fail on
"table already exists". Fix once:

```bash
python -m alembic stamp head          # record baseline as applied, without running it
python -m alembic upgrade head        # apply anything newer
```
`AUTO_MIGRATE=true` does this stamp automatically when it detects pre-existing tables and no
`alembic_version` row.

## If a migration fails halfway

1. Stop traffic (or the writes).
2. `python -m alembic current` — note the revision; do **not** re-run blindly.
3. Take a backup of the current state.
4. Fix forward with a new revision if the partial state is recoverable; otherwise restore from
   [`backup-restore.md`](backup-restore.md) and roll the code back ([`rollback.md`](rollback.md)).
5. Postgres: `alembic upgrade` runs in a transaction per revision; SQLite DDL is not fully
   transactional — prefer the restore path there.
