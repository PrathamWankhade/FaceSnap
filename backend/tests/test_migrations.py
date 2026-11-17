"""Schema bootstrap: fresh upgrade, pre-Alembic stamp, and idempotence."""
import sqlite3

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.db import Base
from app.migrations import BASELINE_REVISION, alembic_config, schema_state, upgrade_to_head


def _engine(tmp_path):
    path = tmp_path / "migrate.db"
    return create_engine(f"sqlite:///{path}"), path


def _head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def test_fresh_database_reaches_head_with_the_partial_index(tmp_path):
    engine, path = _engine(tmp_path)
    upgrade_to_head(engine)

    has_tables, has_version = schema_state(engine)
    assert (has_tables, has_version) == (True, True)

    with sqlite3.connect(path) as connection:
        version = connection.execute("select version_num from alembic_version").fetchall()
        indexes = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='index'"
            )
        }
    assert version == [(_head_revision(),)]
    assert "uq_attendance_daily" in indexes


def test_pre_alembic_schema_is_stamped_not_replayed(tmp_path):
    engine, path = _engine(tmp_path)
    # Simulate a database created by the old create_all() startup path.
    Base.metadata.create_all(bind=engine)
    assert schema_state(engine) == (True, False)

    upgrade_to_head(engine)

    assert schema_state(engine) == (True, True)
    with sqlite3.connect(path) as connection:
        version = connection.execute("select version_num from alembic_version").fetchall()
        student_columns = {
            row[1] for row in connection.execute("pragma table_info(students)")
        }
    assert version == [(_head_revision(),)]
    assert "roll_number" in student_columns
    assert "consent_version" in student_columns


def test_upgrade_is_idempotent(tmp_path):
    engine, _path = _engine(tmp_path)
    upgrade_to_head(engine)
    upgrade_to_head(engine)

    with engine.connect() as connection:
        assert inspect(connection).has_table("alembic_version")
        assert inspect(connection).has_table("attendance")


def test_pre_consent_database_gains_the_new_columns(tmp_path):
    """The real migration path: baseline existed, the consent revision did not."""
    engine, path = _engine(tmp_path)
    config = alembic_config(engine)
    command.upgrade(config, BASELINE_REVISION)
    # Simulate a create_all-era database: schema present, no revision stamped.
    with sqlite3.connect(path) as connection:
        connection.execute("drop table alembic_version")

    upgrade_to_head(engine)

    with sqlite3.connect(path) as connection:
        version = connection.execute("select version_num from alembic_version").fetchall()
        columns = {row[1] for row in connection.execute("pragma table_info(students)")}
    assert version == [(_head_revision(),)]
    assert {"consent_version", "consent_at"} <= columns


def test_empty_alembic_version_table_does_not_replay_the_baseline(tmp_path):
    """A failed first attempt can leave the version table created but empty."""
    engine, path = _engine(tmp_path)
    Base.metadata.create_all(bind=engine)
    with sqlite3.connect(path) as connection:
        connection.execute("create table alembic_version (version_num varchar(32) not null)")

    upgrade_to_head(engine)

    with sqlite3.connect(path) as connection:
        version = connection.execute("select version_num from alembic_version").fetchall()
        columns = {row[1] for row in connection.execute("pragma table_info(students)")}
    assert version == [(_head_revision(),)]
    assert "consent_version" in columns
