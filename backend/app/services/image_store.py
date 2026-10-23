"""Minimal local object store for face images.

Keeps biometric originals out of the database (and out of Firestore-sized
documents). Swap ``FACE_IMAGE_DIR`` for an S3/MinIO-backed implementation
later without touching the API layer.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from app.config import FACE_IMAGE_DIR
from app.services.face_service import MAX_IMAGE_BYTES


def _root() -> Path:
    path = Path(FACE_IMAGE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def decode_data_url(data_url: str) -> bytes:
    """Accept both raw base64 and ``data:image/...;base64,`` payloads."""
    if not data_url:
        raise ValueError("Empty image payload.")
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        return base64.b64decode(raw, validate=True)
    except Exception as exc:  # noqa: BLE001 - surface a clean error
        raise ValueError("Invalid base64 image data.") from exc


def save(student_id: str, data_url: str) -> str:
    data = decode_data_url(data_url)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large (max {MAX_IMAGE_BYTES // (1024 * 1024)}MB).")
    key = f"{student_id}.jpg"
    (_root() / key).write_bytes(data)
    return key


def load(key: str | None) -> bytes | None:
    if not key:
        return None
    path = _root() / key
    if not path.exists():
        return None
    return path.read_bytes()


def delete(key: str | None) -> None:
    if not key:
        return
    path = _root() / key
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def key_for(student_id: str) -> str:
    return f"{student_id}.jpg"
