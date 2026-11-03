"""Alembic environment for FaceSnap.

The migration URL is taken from ``app.config.DATABASE_URL`` (i.e. the same
``backend/.env`` / environment the application uses) so migrations can never
silently target a different database than the app.

Configured here rather than in ``alembic.ini`` for exactly that reason.
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable when alembic is invoked from the repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL  # noqa: E402
from app.db import Base, engine as app_engine  # noqa: E402  (imports every model)

config = context.config

# Escape % for configparser's interpolation; keep app and migrations aligned.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None and not config.attributes.get("disable_logger", False):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (``alembic upgrade --sql``)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=DATABASE_URL.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    # The application engine already has the right connect_args for SQLite
    # (check_same_thread=False) and pool settings; reuse it instead of
    # building a second engine that might differ. A fresh connection is used
    # every call so repeated ``alembic`` invocations in one process never see a
    # closed connection cached from a previous command.
    connectable = app_engine.connect()

    context.configure(
        connection=connectable,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite cannot ALTER most things in place; batch mode rewrites the table.
        render_as_batch=DATABASE_URL.startswith("sqlite"),
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connectable.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
