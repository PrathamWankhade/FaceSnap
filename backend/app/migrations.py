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
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger("facesnap.migrations")

BACKEND_DIR = Path(__file__).resolve().parents[1]


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


def upgrade_to_head(engine: Engine) -> None:
    """Bring the database to head, stamping a pre-Alembic schema first."""
    has_tables, has_version = schema_state(engine)
    config = alembic_config(engine)
    if has_tables and not has_version:
        logger.warning(
            "Existing schema without alembic_version; stamping the baseline revision."
        )
        command.stamp(config, "head")
    command.upgrade(config, "head")
    logger.info("Database schema is at Alembic head.")
