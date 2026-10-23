import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# ArcFace recognition threshold (cosine distance, lower = stricter match)
ARCFACE_THRESHOLD = 0.35

# Embedding dimension (InsightFace ArcFace = 512)
EMBEDDING_DIM = 512

# Face detection confidence threshold
DETECTION_CONFIDENCE = 0.5

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Camera
PI_CAMERA_ENABLED = os.getenv("PI_CAMERA_ENABLED", "false").lower() == "true"

# Vector DB (persistent by default so embeddings survive restarts)
QDRANT_PATH = os.getenv("QDRANT_PATH", "./data/qdrant")

# Relational database (system of record). SQLite for dev, Postgres in prod.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./facesnap.db")

# Local face-image store (swap for S3/MinIO in production)
FACE_IMAGE_DIR = os.getenv("FACE_IMAGE_DIR", "./data/faces")

# Comma-separated emails granted the admin role on first login.
ADMIN_EMAILS = [
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "prathamwankhade2004@gmail.com").split(",")
    if email.strip()
]

# Liveness detection
LIVENESS_FRAME_COUNT = 30
LIVENESS_FPS_TARGET = 30
LIVENESS_HEARTBEAT_MIN = 0.5
LIVENESS_HEARTBEAT_MAX = 3.0
LIVENESS_SCORE_THRESHOLD = 0.5
# A clear photoplethysmographic signal on its own is strong evidence of a live
# face; without this, users who sit still and do not blink in the 1-2s capture
# window are rejected even when a pulse is present.
LIVENESS_RPPG_PASS = float(os.getenv("LIVENESS_RPPG_PASS", "0.6"))
