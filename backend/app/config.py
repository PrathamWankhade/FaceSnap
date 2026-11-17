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

# Enrollment quality gates. A bad enrollment poisons every later match, so the
# server rejects blurry, tiny, dark, off-angle or ambiguous photos instead of
# storing them. Thresholds are deliberately conservative and configurable.
ENROLLMENT_MIN_FACE_PX = int(os.getenv("ENROLLMENT_MIN_FACE_PX", "100"))
ENROLLMENT_MIN_DET_SCORE = float(os.getenv("ENROLLMENT_MIN_DET_SCORE", "0.60"))
ENROLLMENT_MIN_SHARPNESS = float(os.getenv("ENROLLMENT_MIN_SHARPNESS", "35"))
ENROLLMENT_MIN_BRIGHTNESS = float(os.getenv("ENROLLMENT_MIN_BRIGHTNESS", "40"))
ENROLLMENT_MAX_YAW = float(os.getenv("ENROLLMENT_MAX_YAW", "0.35"))
ENROLLMENT_MAX_ROLL = float(os.getenv("ENROLLMENT_MAX_ROLL", "25"))

# Reject enrolling the same face under a second identity. Cosine distance at or
# below this is treated as a duplicate. Strict on purpose: a false duplicate
# blocks one student who can retry, a missed duplicate creates a fraud path.
DUPLICATE_FACE_DISTANCE = float(os.getenv("DUPLICATE_FACE_DISTANCE", "0.30"))

# Consent version recorded at enrollment. Bump when the notice or the data
# practice changes so existing rows can be identified and re-consented.
CONSENT_VERSION = os.getenv("CONSENT_VERSION", "2026-11").strip()

# Recognition model identifier recorded on each enrollment. Bump (or set via
# env) when the backbone changes so the institution knows which students need
# re-enrollment. This is metadata only; the embedding dimension is unchanged.
MODEL_VERSION = os.getenv("MODEL_VERSION", "buffalo_s").strip()

# Alerting: optional webhook fired on health degradation or error-rate spikes.
# Empty disables alerting entirely (the safe default for local development).
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
ALERT_ERROR_RATE_THRESHOLD = float(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "0.1"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
# Minimum requests before an error-rate alert can fire (avoids noise on tiny samples).
ALERT_MIN_REQUESTS = int(os.getenv("ALERT_MIN_REQUESTS", "20"))

# Persist unmatched detections for staff review. Off disables the queue entirely.
REVIEW_QUEUE_ENABLED = _env_bool("REVIEW_QUEUE_ENABLED", default=True)

# Attendance retention. 0 keeps rows forever (the safe default until the
# institution sets a policy). Used by scripts/purge_retention.py, not at startup.
ATTENDANCE_RETENTION_DAYS = int(os.getenv("ATTENDANCE_RETENTION_DAYS", "0"))

# Conditional low-light enhancement applied before detection/embedding.
# A frame at or above the threshold is left untouched; a darker frame is
# CLAHE+gamma lifted toward the target mean, with a capped gain.
LOW_LIGHT_THRESHOLD = float(os.getenv("LOW_LIGHT_THRESHOLD", "90"))
LOW_LIGHT_TARGET_MEAN = float(os.getenv("LOW_LIGHT_TARGET_MEAN", "115"))
LOW_LIGHT_MAX_GAMMA = float(os.getenv("LOW_LIGHT_MAX_GAMMA", "3.0"))

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# CORS. Wildcard is a development convenience only; production must be explicit.
_cors_default = "" if IS_PRODUCTION else "*"
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", _cors_default).split(",") if origin.strip()]

# Per-IP limit for the expensive face/verify endpoints. 0 disables the limiter.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
# "memory" (single worker) or "redis" (shared across workers). The Redis client
# is imported lazily, so the memory backend has no extra dependency.
RATE_LIMIT_BACKEND = os.getenv("RATE_LIMIT_BACKEND", "memory").strip().lower()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()

# Only trust X-Forwarded-For when the app is actually behind a reverse proxy
# you control; otherwise clients can spoof the header to dodge rate limits.
TRUST_PROXY_HEADERS = _env_bool("TRUST_PROXY_HEADERS", default=False)

# Camera
PI_CAMERA_ENABLED = _env_bool("PI_CAMERA_ENABLED", default=False)
PI_SERVICE_KEY = os.getenv("PI_SERVICE_KEY", "").strip()

# Vector DB (persistent by default so embeddings survive restarts)
QDRANT_PATH = os.getenv("QDRANT_PATH", "./data/qdrant")

# Relational database (system of record). SQLite for dev, Postgres in prod.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./facesnap.db")

# Apply Alembic migrations at startup. Off by default so a local checkout keeps
# the create_all fast path; the Docker image and production deploys enable it.
AUTO_MIGRATE = _env_bool("AUTO_MIGRATE", default=False)

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

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json" if IS_PRODUCTION else "text")

# Health timeouts (seconds). Dependencies slower than this count as unhealthy.
HEALTH_DB_TIMEOUT = float(os.getenv("HEALTH_DB_TIMEOUT", "2.0"))
HEALTH_VECTOR_TIMEOUT = float(os.getenv("HEALTH_VECTOR_TIMEOUT", "2.0"))
