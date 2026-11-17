"""Schema bootstrap via Alembic.

Migrations are the canonical schema path (ADR 0005). Two startup cases exist:

* **Fresh database** — no tables: run every migration to ``head``.
* **Pre-Alembic database** — the app previously created tables with
  ``Base.metadata.create_all`` and has no ``alembic_version`` row. Replaying the
  baseline would fail on existing tables, so the database is stamped at the
  baseline revision and upgraded from there. ``alembic stamp head`` is the
  documented manual equivalent (``docs/runbooks/migrate.md``).

Set ``AUTO_MIGRATE=true`` to run this at startup (the Docker image does). Without
it, ``init_db`` keeps the legacy ``create_all`` behaviour so a local checkout
still boots; production should run ``alembic upgrade head`` as a deploy step.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("facesnap.migrations")

BACKEND_DIR = Path(__file__).resolve().parents[1]

# The first revision. A create_all-era database already contains that schema,
# so it is stamped at the baseline and then upgraded — stamping *head* would
# skip every later migration (and silently omit new columns).
BASELINE_REVISION = "5a3501be40cf"


def alembic_config(engine: Engine | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    # Absolute script location: the app may be started from any working directory.
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["disable_logger"] = True
    if engine is not None:
        config.attributes["engine"] = engine
    return config


def schema_state(engine: Engine) -> tuple[bool, bool]:
    """Return ``(has_application_tables, has_alembic_version)``."""
    with engine.connect() as connection:
        inspector = inspect(connection)
        has_tables = inspector.has_table("students") or inspector.has_table("users")
        has_version = inspector.has_table("alembic_version")
    return has_tables, has_version


def _has_version_row(engine: Engine) -> bool:
    """Whether ``alembic_version`` exists *and* names a revision.

    An empty table is possible after a failed upgrade attempt; treating it as
    "already stamped" would replay the baseline into existing tables.
    """
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return False
        try:
            value = connection.execute(
                text("select version_num from alembic_version limit 1")
            ).scalar()
        except SQLAlchemyError:
            return False
    return bool(value)


def upgrade_to_head(engine: Engine) -> None:
    """Bring the database to head, stamping a pre-Alembic schema first."""
    has_tables, _has_version_table = schema_state(engine)
    config = alembic_config(engine)
    if has_tables and not _has_version_row(engine):
        logger.warning(
            "Existing schema without an Alembic revision; stamping baseline %s.",
            BASELINE_REVISION,
        )
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")
    logger.info("Database schema is at Alembic head.")
