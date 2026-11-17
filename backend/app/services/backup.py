"""SQLite backup/restore helpers used by the runbook and its test.

SQLite's online backup API copies a consistent database even while it is open,
which is why ``cp facesnap.db backup.db`` is not the documented procedure. A
Postgres deployment should use ``pg_dump``/``pg_restore`` instead; this module
deliberately refuses to pretend otherwise.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def _copy(source: Path, target: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"database not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target


def sqlite_backup(source: Path | str, target: Path | str) -> Path:
    """Write a consistent copy of ``source`` to ``target``."""
    return _copy(Path(source), Path(target))


def sqlite_restore(backup: Path | str, target: Path | str) -> Path:
    """Restore ``backup`` over ``target`` (which may already exist)."""
    return _copy(Path(backup), Path(target))
