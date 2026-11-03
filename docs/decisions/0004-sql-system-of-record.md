# ADR 0004: SQL is the system of record; Firebase is identity only

**Date:** 2026-10-15 · **Status:** Accepted (supersedes the original Firestore-backed design)

## Context

FaceSnap originally mirrored users and attendance into Firestore and used Firebase Storage for
photos. That produced two systems of record: the client could write one while the backend read the
other. Role checks had to run client-side, error handling had to branch on two backends, and no
SQL constraint could protect attendance integrity. Removal of the fallback code cut ~2 files and
every duplicated error path.

## Decision

1. **Firebase Auth is identity only.** Its ID token answers "who is calling". It is never a
   source of roles, attendance or profile data.
2. **A relational database (SQLAlchemy; SQLite locally, `DATABASE_URL` to Postgres when deployed)
   is the single system of record** for `users`, `students`, `courses`, `class_sessions`,
   `attendance`, `leave_requests`, `cameras`, `audit_log`.
3. **Authorization reads `users.role` from SQL** (`app/auth.py`), never token claims.
4. **Qdrant and the image store are derived/supporting stores**, rebuildable from SQL
   (`POST /api/admin/backfill-embeddings`).
5. **No Firestore/Storage code paths remain** and must not be reintroduced.

## Consequences

- Real foreign keys: attendance history survives profile edits; deleting a student cascades.
- Database-enforced integrity (unique constraints, partial unique index) covers races that
  application checks cannot.
- One error model, one permission matrix, one set of tests.
- Migration story becomes necessary → see [`0005`](0005-alembic-migrations.md).
- Firebase project is still required for SSO; `firebase-admin` only verifies tokens.

## Alternatives considered

- **Firestore as system of record** — weaker constraints, client-writable, dual-write drift.
- **Trusting token claims for roles** — claims are minted by an identity provider that does not
  know our roles; they also go stale between refreshes.
