# CLAUDE.md

The single project memory file is [`AGENTS.md`](AGENTS.md) — read that first.

Short version:

```bash
# backend
cd backend && python -m pytest -q && python -m ruff check app tests

# frontend
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

Non-negotiables: the browser never writes attendance, the SQL database is the system of record,
roles come from `users.role` in SQL, production fails closed, no biometrics/secrets in git, and no
claims we have not tested. Full rules, commands, layout and doc map: `AGENTS.md`.
