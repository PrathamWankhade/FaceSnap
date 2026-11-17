"""SQLite backup/restore round trip (the mechanism the runbook depends on)."""
import sqlite3

import pytest

from app.services.backup import sqlite_backup, sqlite_restore


def _make_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("create table students (id text primary key, name text)")
        connection.execute("insert into students values ('s1', 'Ada')")


def _names(path):
    with sqlite3.connect(path) as connection:
        return [row[0] for row in connection.execute("select name from students")]


def test_backup_is_a_consistent_copy(tmp_path):
    source = tmp_path / "facesnap.db"
    _make_database(source)

    backup = sqlite_backup(source, tmp_path / "backups" / "facesnap.db")

    assert backup.exists()
    assert _names(backup) == ["Ada"]
    # The source is untouched.
    assert _names(source) == ["Ada"]


def test_restore_replaces_the_target(tmp_path):
    source = tmp_path / "facesnap.db"
    _make_database(source)
    backup = sqlite_backup(source, tmp_path / "backup.db")

    target = tmp_path / "restored.db"
    with sqlite3.connect(target) as connection:
        connection.execute("create table stale (id integer)")

    sqlite_restore(backup, target)

    with sqlite3.connect(target) as connection:
        tables = {row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
        assert "students" in tables
    assert _names(target) == ["Ada"]


def test_missing_source_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        sqlite_backup(tmp_path / "nope.db", tmp_path / "out.db")
