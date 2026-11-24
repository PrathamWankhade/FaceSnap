"""AES-256-GCM encryption for enrollment photos at rest.

Why application-level encryption: the documented threat in
``docs/SECURITY.md`` is a stolen disk or backup of ``FACE_IMAGE_DIR``.
Volume encryption covers that at the host level; this module covers the
case where the app's own storage directory is copied without the host.

Scope (deliberately narrow):
  * **Enrollment photos** are encrypted on write and decrypted on read.
  * **Embeddings in Qdrant are NOT encrypted here** — cosine similarity
    needs plaintext vectors. Qdrant-level controls are documented in
    ``docs/hosting.md`` as a deployment responsibility.
  * If no key is configured, encryption is a **transparent passthrough** so
    existing dev databases and tests behave exactly as before. A malformed
    key refuses to boot (see ``app/config.py``).

File format (self-describing, versioned):
    b"FSENC1" || nonce(12) || AESGCM ciphertext+tag
A file without the magic header is assumed to be legacy plaintext and is
returned unchanged; an encrypted file with no/wrong key fails closed.
"""
from __future__ import annotations

import base64
import os

MAGIC = b"FSENC1"
NONCE_LEN = 12
AAD = b"facesnap-biometric-v1"
KEY_LEN = 32  # AES-256

_MISSING = object()


def validate_key(raw: str) -> bytes:
    """Decode and validate a base64 32-byte key. Raises ValueError (never logs it)."""
    if not raw or not raw.strip():
        raise ValueError("Key must not be empty.")
    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except Exception as exc:
        raise ValueError(
            "BIOMETRIC_ENCRYPTION_KEY must be base64 (e.g. `python -c "
            "'import base64,os;print(base64.b64encode(os.urandom(32)).decode())'`)."
        ) from exc
    if len(key) != KEY_LEN:
        raise ValueError(f"BIOMETRIC_ENCRYPTION_KEY must decode to 32 bytes, got {len(key)}.")
    return key


def generate_key() -> str:
    """Convenience for operators: a fresh base64 key (printed to stdout only)."""
    return base64.b64encode(os.urandom(KEY_LEN)).decode()


def _active_key():
    """Read the configured key lazily so this module never imports app.config
    at module level (config imports this module for startup validation)."""
    from app.config import BIOMETRIC_ENCRYPTION_KEY

    return BIOMETRIC_ENCRYPTION_KEY or None


def key_material() -> bytes | None:
    """Validated key bytes, or None when encryption is disabled."""
    raw = _active_key()
    if not raw:
        return None
    return validate_key(raw)


def is_enabled() -> bool:
    return bool(_active_key())


def is_encrypted(data: bytes) -> bool:
    return data[: len(MAGIC)] == MAGIC


def encrypt(plaintext: bytes) -> bytes:
    """Encrypt with AES-256-GCM. Passthrough (unchanged bytes) when disabled."""
    if not plaintext:
        return plaintext
    key = key_material()
    if key is None:
        return plaintext
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(NONCE_LEN)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)
    return MAGIC + nonce + ciphertext


def decrypt(data: bytes) -> bytes:
    """Decrypt an encrypted blob. Legacy plaintext passes through untouched;
    an encrypted blob with no key or a wrong key raises ValueError."""
    if not data or not is_encrypted(data):
        return data
    key = key_material()
    if key is None:
        raise ValueError(
            "Data is encrypted but no BIOMETRIC_ENCRYPTION_KEY is configured."
        )
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    body = data[len(MAGIC) :]
    nonce, ciphertext = body[:NONCE_LEN], body[NONCE_LEN:]
    if len(nonce) != NONCE_LEN or not ciphertext:
        raise ValueError("Encrypted payload is truncated.")
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, AAD)
    except InvalidTag as exc:
        # Wrong key or tampered bytes. Never log the key or the plaintext.
        raise ValueError("Decryption failed (wrong key or tampered data).") from exc