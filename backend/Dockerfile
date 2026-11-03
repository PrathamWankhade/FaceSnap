# FaceSnap backend (FastAPI recognition service).
#
# Build:
#   docker build -t facesnap-backend -f backend/Dockerfile .
# Run standalone (dev, SQLite):
#   docker run --rm -p 8000:8000 \
#     -e APP_ENV=development -e REQUIRE_AUTH=false \
#     -e CORS_ORIGINS=http://localhost:3000 \
#     facesnap-backend
#
# Production should mount persistent volumes for:
#   - ./data/faces   -> /app/data/faces   (biometric originals)
#   - ./data/qdrant  -> /app/data/qdrant  (derived vector index)
#   - a Postgres DSN via DATABASE_URL
# See docs/hosting.md.
FROM python:3.11-slim AS builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for psycopg (optional prod driver) and model runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

FROM python:3.11-slim AS runtime

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATABASE_URL=sqlite:///./facesnap.db \
    QDRANT_PATH=/app/data/qdrant \
    FACE_IMAGE_DIR=/app/data/faces \
    PORT=8000 \
    HOST=0.0.0.0 \
    PI_CAMERA_ENABLED=false

# Non-root user for defence in depth.
RUN groupadd -r facesnap && useradd -r -g facesnap -d /app -s /sbin/nologin facesnap

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY backend/app ./app
COPY backend/alembic.ini backend/alembic.ini
COPY backend/alembic ./alembic

# Persistent, derived-store directories (empty here; mount volumes in prod).
RUN mkdir -p /app/data/faces /app/data/qdrant && \
    chown -R facesnap:facesnap /app

USER facesnap

# Apply migrations before serving (expand/contract safe; single replica).
# For multi-replica prod, set AUTO_MIGRATE=false and run `alembic upgrade head`
# as a separate deploy step instead.
ENV AUTO_MIGRATE=true
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=2)" || exit 1
CMD ["sh", "-c", "python -m alembic upgrade head && exec uvicorn app.main:app --host ${HOST} --port ${PORT}"]
