"""Minimal local object store for face images.

Keeps biometric originals out of the database (and out of Firestore-sized
documents). Swap ``FACE_IMAGE_DIR`` for an S3/MinIO-backed implementation
later without touching the API layer.

When ``BIOMETRIC_ENCRYPTION_KEY`` is configured, files are written with
AES-256-GCM application-level encryption (see ``biometric_crypto``). Reading
is format-aware: encrypted files decrypt, legacy plaintext passes through,
and an encrypted file with no key fails closed instead of leaking bytes.
"""
from __future__ import annotations

import base64
from pathlib import Path

from app.services.biometric_crypto import decrypt, encrypt
from app.services.face_service import MAX_IMAGE_BYTES


def _root() -> Path:
    # Read the directory from config on every call: tests and scripts redirect
    # ``app.config.FACE_IMAGE_DIR`` at runtime, and an import-time binding would
    # silently keep writing to the configured production directory.
    from app.config import FACE_IMAGE_DIR as configured_dir

    path = Path(configured_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def decode_data_url(data_url: str) -> bytes:
    """Accept both raw base64 and ``data:image/...;base64,`` payloads."""
    if not data_url:
        raise ValueError("Empty image payload.")
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        return base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 image data.") from exc


def save(student_id: str, data_url: str) -> str:
    data = decode_data_url(data_url)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large (max {MAX_IMAGE_BYTES // (1024 * 1024)}MB).")
    save_bytes(student_id, data, suffix=".jpg")
    return key_for(student_id)


def save_bytes(student_id: str, data: bytes, suffix: str = ".jpg") -> str:
    """Write raw (already decoded) bytes, encrypted when configured.

    Used by the enrollment path and by ``scripts/encrypt_photos.py`` so both
    go through the exact same on-disk format.
    """
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large (max {MAX_IMAGE_BYTES // (1024 * 1024)}MB).")
    key = f"{student_id}{suffix}"
    (_root() / key).write_bytes(encrypt(data))
    return key


def list_keys(root: Path | None = None) -> list[str]:
    """All photo keys currently on disk (for migration scripts)."""
    base = root if root is not None else _root()
    return sorted(p.name for p in base.glob("*.jpg"))


def load(key: str | None) -> bytes | None:
    if not key:
        return None
    path = _root() / key
    if not path.exists():
        return None
    return decrypt(path.read_bytes())


def exists(key: str | None) -> bool:
    """Whether a photo is on disk (used by deletion verification)."""
    if not key:
        return False
    return (_root() / key).exists()


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
