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

# Qdrant
QDRANT_PATH = os.getenv("QDRANT_PATH", ":memory:")

# Liveness detection
LIVENESS_FRAME_COUNT = 30
LIVENESS_FPS_TARGET = 30
LIVENESS_HEARTBEAT_MIN = 0.5
LIVENESS_HEARTBEAT_MAX = 3.0
LIVENESS_SCORE_THRESHOLD = 0.5