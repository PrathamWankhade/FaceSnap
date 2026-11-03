# ADR 0005: Schema changes go through Alembic migrations

**Date:** 2026-10-23 · **Status:** Accepted

## Context

The schema was created by `Base.metadata.create_all()` at startup. That is fine for a greenfield
SQLite file and wrong for anything shared:

- `create_all` can only *add* tables; it never alters or drops columns, so a schema change silently
  no-ops on an existing database and the app breaks at query time.
- Nobody can tell which version a deployed database is in.
- A rollback has no counterpart: there is no `downgrade`.

## Decision

1. **Alembic owns schema evolution.** The canonical command is
   `python -m alembic upgrade head` (see [`../runbooks/migrate.md`](../runbooks/migrate.md)).
2. **Migrations are generated from models** (`alembic revision --autogenerate`) and are **reviewed
   by hand** — autogenerate misses partial indexes and server defaults.
3. The partial unique index `uq_attendance_daily`
   (`attendance (student_id, method, date(captured_at)) WHERE session_id IS NULL`) is part of the
   baseline migration and must survive every `upgrade`/`downgrade` cycle; it is a correctness
   guarantee, not an optimisation (see NFR-C2).
4. **Startup applies migrations when `AUTO_MIGRATE=true`** (default in development and containers).
   Production may set `AUTO_MIGRATE=false` and run migrations as a separate deploy step/runbook.
5. `create_all()` remains only as the fallback for `AUTO_MIGRATE=false` on an empty/dev database
   and for tests, which build and drop their own schema.
6. **Every schema change ships a migration in the same commit as the model change**, and must be
   verified against a **fresh** database as well as an existing one.

## Consequences

- Deploy = back up → `alembic upgrade head` → start new code (runbook linked above).
- Rollback = deploy previous code → `alembic downgrade -1`, with the caveat that destructive
  downgrades are forbidden unless data loss is explicitly accepted in the migration docstring.
- CI proves `upgrade head` succeeds on a clean database, and that the model and migration agree
  (autogenerate produces no diff).

## Alternatives considered

- **Keep `create_all`** — no downgrade path, invisible schema drift, false confidence.
- **ORM-only "migration" (drop and recreate)** — destroys attendance data; unacceptable.
