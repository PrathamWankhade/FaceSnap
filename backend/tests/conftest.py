"""Test environment: isolated SQLite file, object store, and in-memory vectors.

These must be set before the application modules import ``app.db``/``app.config``.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="facesnap-tests-")

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(_TMP, 'test.db').replace(os.sep, '/')}")
os.environ.setdefault("FACE_IMAGE_DIR", os.path.join(_TMP, "faces"))
os.environ.setdefault("QDRANT_PATH", ":memory:")
os.environ.setdefault("REQUIRE_AUTH", "false")
