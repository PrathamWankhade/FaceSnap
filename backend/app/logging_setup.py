"""Application logging setup.

Development: human-readable lines on stderr.
Production: structured JSON on stdout so a log shipper can ingest it.
Call once at process start (``backend/app/main.py`` import time).
"""
from __future__ import annotations

import logging
import sys

from app.config import IS_PRODUCTION, LOG_LEVEL


def configure_logging() -> None:
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    handler = logging.StreamHandler(sys.stdout if IS_PRODUCTION else sys.stderr)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Third-party loggers are noisy at INFO; keep them quieter unless asked otherwise.
    for name in ("uvicorn", "uvicorn.access", "sqlalchemy.engine", "qdrant_client"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("facesnap.request").setLevel(level)
