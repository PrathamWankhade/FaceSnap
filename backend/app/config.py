import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Recognition threshold (Euclidean distance)
RECOGNITION_THRESHOLD = 0.85

# YOLO confidence threshold
YOLO_CONFIDENCE = 0.3

# FaceNet input size
FACENET_INPUT_SIZE = (160, 160)

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Camera
PI_CAMERA_ENABLED = os.getenv("PI_CAMERA_ENABLED", "false").lower() == "true"
