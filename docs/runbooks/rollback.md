# Runbook: rollback

Use when a deploy misbehaves: 5xx spike, wrong behaviour, failed health check, or a migration that
turned out to be wrong. **Decide to roll back first, investigate second.**

## 1. Assess (60 seconds)

```bash
curl -fsS $API/api/health | head        # ok? which component?
```
- Health red or process not starting → roll back **now** (step 2), then look at logs.
- Health green but behaviour wrong (data/permissions) → roll back **and** check whether the
  migration is the cause (step 3).

## 2. Roll back the code

```bash
# compose / container host
docker compose up -d --build backend frontend   # from the previous git tag
# or, from a checkout
git checkout <previous-tag>
```
Confirm `/api/health/live` → `200` and `/api/health` → `ok: true` with the expected row counts.

## 3. Roll back the schema (only if the migration is the problem)

```bash
cd backend
python -m alembic current          # where are we?
python -m alembic downgrade -1     # or: <target revision>
python -m alembic current
```

**Read the migration's docstring before downgrading.** Downgrades that drop a column or a table
are *destructive*: rolling the code back but keeping the new schema is often the safer order
("expand/contract": new schema + old code may work; old schema + new code usually does not).
If data loss is unavoidable, take a backup **first** and record who approved it.

## 4. Verify after rollback

- [ ] `/api/health` `ok: true`, row counts sane (not 0)
- [ ] sign-in + `/api/me` work
- [ ] the failing path now behaves as it did before
- [ ] error rate back to baseline in metrics/logs
- [ ] note the revision: `alembic current` matches what the old code expects

## 5. Aftermath

- Keep the failed revision in history; **never rewrite a pushed migration** — add a new one.
- File the defect with the `request_id`s from the incident
  ([`incident-response.md`](incident-response.md)).
- Re-deploy only after the fix has a regression test.

## When rollback is not enough

- **Corrupt/lost data** → [`backup-restore.md`](backup-restore.md).
- **Leaked secret** → rotate the key first, then investigate (see [`../SECURITY.md`](../SECURITY.md)).
- **Auth bypass exposed to a network** → take the process off the network immediately; treat every
  request in that window as unauthenticated traffic and review audit logs.
