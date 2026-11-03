# Runbook: incident response

For the person who just got paged (or noticed). There is **no on-call rotation** for this project
today — see [`../hosting.md`](../hosting.md) § decisions owed — so this is the procedure one
maintainer follows.

## 0. Triage (first 5 minutes)

Ask, in order:

1. **Are users failing?** Check `/api/health/live` and `/api/health` from outside your machine.
2. **Which component?** `database_ready` / `vector_db_ready` / `face_model_ready` / `camera` in the
   health payload tells you *where* to look. Do not guess.
3. **Did we ship?** `git log` + last deploy time ([`deploy.md`](deploy.md) step 7). A regression
   that started minutes after a deploy is the most common cause — roll back first
   ([`rollback.md`](rollback.md)), investigate second.
4. **Is it data or availability?** Wrong/missing attendance rows are an integrity incident
   (§2); 5xx/timeouts are availability (§1).

Grab 2–3 `X-Request-Id` values from failing responses — they key every log line.

## 1. Availability incident

- [ ] Confirm with `curl -fsS $API/api/health` (outside the app).
- [ ] Tail structured logs filtered by `request_id`, then by `level=ERROR`; look for the traceback.
- [ ] Check `face_model_ready` — a missing/failed model load returns `503` on recognition routes
      by design; that is a deploy/image problem, not a code bug.
- [ ] Check rate limiting: a `429` storm from one host means a runaway client, not abuse.
- [ ] If introduced by the deploy → roll back, then fix forward.
- [ ] If the database is the cause (disk, locks, wrong `DATABASE_URL`) → **stop here**, take a
      backup, then [`backup-restore.md`](backup-restore.md).

## 2. Data / integrity incident (wrong or missing attendance)

Assume writes may have been accepted when they should not have been.

- [ ] **Stop writes** (scale to zero, or take the API offline). Preserving state beats uptime here.
- [ ] **Backup current state immediately** — `scripts/backup.sh` — even if you suspect it is bad.
- [ ] Identify the blast radius from `audit_log` (actor, action, entity, timestamp) and the
      `attendance` rows in the window, joined to `students` for context:
      `SELECT id, student_id, method, captured_at, recorded_by, distance, liveness_score
       FROM attendance WHERE captured_at BETWEEN ? AND ?;`
- [ ] Classify: double-marks (should be impossible — the partial unique index guards them),
      marks for a non-matching face, marks written by the wrong role, or a mis-migrated schema.
- [ ] Decide the correction with the data owner (institution): leave as-is with a note, or delete
      specific rows. **Never bulk-delete without an exported copy of what you are removing.**
- [ ] Fix forward with a migration/code change **plus a regression test** that reproduces it.

## 3. Security incident

Follow [`../SECURITY.md`](../SECURITY.md). Short version:

- **Leaked secret** (Groq key, service account, `PI_SERVICE_KEY`, ID token in a log/screenshot):
  rotate the credential **first**, revoke the old one, then find the blast radius. Assume committed
  history is compromised — a rewrite does not un-leak a published key.
- **Auth bypass reached a network** (`REQUIRE_AUTH=false` exposed): disconnect the process,
  treat every request in the window as unauthenticated, review `audit_log` and proxy logs, then
  fix the config and confirm `_validate_runtime()` refuses to boot it.
- **Biometric data exposed** (photos/DB reachable): rotate anything in the same store, take it
  down, preserve logs, and notify the institution — this is a privacy event, not just an outage.
- Report anything you cannot contain: GitHub **private** security advisory, never a public issue.

## 4. Close out

- [ ] Health `ok: true`, metrics at baseline, the risky path smoke-tested.
- [ ] Write down: timeline, `request_id`s, trigger, blast radius, fix, and **what let it happen**.
- [ ] Regression test for the failure mode; CI green before the next deploy.
- [ ] Update the runbook if you had to improvise — improvisation that works once is the next
      incident's missing step.
