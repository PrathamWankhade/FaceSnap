import os
from pathlib import Path

# Load backend/.env for local development. Real environment variables always
# win, so production/CI configuration is never overridden by a checked-out file.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    pass

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# "development" (default) or "production". Production enables fail-fast checks.
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

# Auth is opt-out only in development. Production defaults to enforcing tokens.
REQUIRE_AUTH = _env_bool("REQUIRE_AUTH", default=IS_PRODUCTION)

# ArcFace recognition threshold (cosine distance, lower = stricter match)
ARCFACE_THRESHOLD = 0.35

# Embedding dimension (InsightFace ArcFace = 512)
EMBEDDING_DIM = 512

# Face detection confidence threshold
DETECTION_CONFIDENCE = 0.5

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# CORS. Wildcard is a development convenience only; production must be explicit.
_cors_default = "" if IS_PRODUCTION else "*"
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", _cors_default).split(",") if origin.strip()]

# Per-IP limit for the expensive face/verify endpoints. 0 disables the limiter.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

# Camera
PI_CAMERA_ENABLED = _env_bool("PI_CAMERA_ENABLED", default=False)
PI_SERVICE_KEY = os.getenv("PI_SERVICE_KEY", "").strip()

# Vector DB (persistent by default so embeddings survive restarts)
QDRANT_PATH = os.getenv("QDRANT_PATH", "./data/qdrant")

# Relational database (system of record). SQLite for dev, Postgres in prod.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./facesnap.db")

# Local face-image store (swap for S3/MinIO in production)
FACE_IMAGE_DIR = os.getenv("FACE_IMAGE_DIR", "./data/faces")

# Comma-separated emails granted the admin role on first login.
ADMIN_EMAILS = [
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
]

# Liveness detection
LIVENESS_FRAME_COUNT = 50
LIVENESS_FPS_TARGET = 10
LIVENESS_HEARTBEAT_MIN = 0.8
LIVENESS_HEARTBEAT_MAX = 3.0
LIVENESS_SCORE_THRESHOLD = 0.5
# A clear photoplethysmographic signal on its own is strong evidence of a live
# face; without this, users who sit still and do not blink in the capture
# window are rejected even when a pulse is present.
LIVENESS_RPPG_PASS = float(os.getenv("LIVENESS_RPPG_PASS", "0.6"))
