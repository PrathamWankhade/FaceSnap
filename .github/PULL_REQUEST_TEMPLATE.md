# PR template for FaceSnap. Fill in what changed and how you verified it.

## Summary
One sentence on what this changes and why.

## Checklist
- [ ] Backend: `python -m pytest -q` passes (`backend/`)
- [ ] Backend: `python -m ruff check app tests` passes
- [ ] Frontend: `npm run lint`, `npx tsc --noEmit`, `npm run build` pass
- [ ] Alembic: if the schema changed, a migration lands in the same commit and `alembic upgrade head` was verified on a fresh DB
- [ ] Docs: `docs/permissions.md` updated for any new/changed route; new irreversible decisions get `docs/decisions/NNNN-title.md`
- [ ] Tests: permission/IDOR coverage added for any route change (`tests/test_permissions.py`)
- [ ] No face photos, `data/`, `*.db`, `.env`, `.env.local`, service-account JSON, or keys committed
- [ ] Groq key stays server-only (`GROQ_API_KEY`, never `NEXT_PUBLIC_`); no secrets printed in logs/output

## Scope
- [ ] This stays within single-institution scope (no org-scoping, billing, or multi-tenancy)
- [ ] Claims stay honest — no "CCTV", "certified anti-spoofing", or "secure by default"

## Manual verification (for camera/SSO changes)
- [ ] Reloaded `/classroom` and `/student` with a real webcam/sign-in (agent cannot do this)

## Reviewer notes
