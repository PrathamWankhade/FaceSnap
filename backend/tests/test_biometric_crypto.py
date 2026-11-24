"""Encryption at rest for enrollment photos: roundtrip, fail-closed, migration."""
import base64
import importlib.util
from pathlib import Path

import pytest

from app.services import biometric_crypto as crypto
from app.services.image_store import exists, load, save

KEY = base64.b64encode(b"k" * 32).decode()
OTHER_KEY = base64.b64encode(b"x" * 32).decode()

DATA_URL = "data:image/jpeg;base64," + base64.b64encode(b"fake-jpeg-bytes").decode()


@pytest.fixture()
def encryption_on(monkeypatch):
    monkeypatch.setattr("app.config.BIOMETRIC_ENCRYPTION_KEY", KEY)


@pytest.fixture()
def encryption_off(monkeypatch):
    monkeypatch.setattr("app.config.BIOMETRIC_ENCRYPTION_KEY", "")


@pytest.fixture()
def photo_dir(tmp_path, monkeypatch):
    directory = tmp_path / "faces"
    monkeypatch.setattr("app.config.FACE_IMAGE_DIR", str(directory))
    return directory


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "encrypt_photos.py"
    spec = importlib.util.spec_from_file_location("encrypt_photos", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Key handling
# ---------------------------------------------------------------------------
def test_validate_key_accepts_32_bytes():
    assert crypto.validate_key(KEY) == b"k" * 32


@pytest.mark.parametrize("bad", ["", "not-base64!!", base64.b64encode(b"short").decode()])
def test_validate_key_rejects_bad_keys(bad):
    with pytest.raises(ValueError):
        crypto.validate_key(bad)


# ---------------------------------------------------------------------------
# Encrypt / decrypt
# ---------------------------------------------------------------------------
def test_roundtrip_produces_versioned_container(encryption_on):
    blob = crypto.encrypt(b"jpeg-bytes")
    assert blob[: len(crypto.MAGIC)] == crypto.MAGIC
    # nonce(12) + ciphertext(plaintext length) + GCM tag(16)
    assert len(blob) == len(crypto.MAGIC) + 12 + len(b"jpeg-bytes") + 16
    assert crypto.decrypt(blob) == b"jpeg-bytes"


def test_encryption_is_randomized_per_write(encryption_on):
    assert crypto.encrypt(b"same") != crypto.encrypt(b"same")


def test_tampered_blob_fails_closed(encryption_on):
    blob = bytearray(crypto.encrypt(b"jpeg-bytes"))
    blob[-1] ^= 0xFF
    with pytest.raises(ValueError):
        crypto.decrypt(bytes(blob))


def test_wrong_key_fails_closed(encryption_on, monkeypatch):
    blob = crypto.encrypt(b"jpeg-bytes")
    monkeypatch.setattr("app.config.BIOMETRIC_ENCRYPTION_KEY", OTHER_KEY)
    with pytest.raises(ValueError):
        crypto.decrypt(blob)


def test_encrypted_data_without_key_raises(encryption_on, monkeypatch):
    blob = crypto.encrypt(b"jpeg-bytes")
    monkeypatch.setattr("app.config.BIOMETRIC_ENCRYPTION_KEY", "")
    with pytest.raises(ValueError):
        crypto.decrypt(blob)


def test_disabled_is_transparent_passthrough(encryption_off):
    assert crypto.encrypt(b"jpeg") == b"jpeg"
    assert crypto.decrypt(b"jpeg") == b"jpeg"


def test_legacy_plaintext_reads_when_encryption_on(encryption_on):
    assert crypto.decrypt(b"\xff\xd8legacy") == b"\xff\xd8legacy"


# ---------------------------------------------------------------------------
# image_store integration
# ---------------------------------------------------------------------------
def test_save_writes_ciphertext_and_load_decrypts(photo_dir, encryption_on):
    key = save("s1", DATA_URL)
    on_disk = (photo_dir / key).read_bytes()
    assert on_disk[: len(crypto.MAGIC)] == crypto.MAGIC
    assert b"fake-jpeg-bytes" not in on_disk
    assert load(key) == b"fake-jpeg-bytes"
    assert exists(key) is True


def test_save_without_key_keeps_plaintext(photo_dir, encryption_off):
    key = save("s1", DATA_URL)
    assert (photo_dir / key).read_bytes() == b"fake-jpeg-bytes"


def test_load_missing_key_returns_none(photo_dir, encryption_on):
    assert load("nope.jpg") is None
    assert exists("nope.jpg") is False


# ---------------------------------------------------------------------------
# Legacy photo migration script
# ---------------------------------------------------------------------------
def test_script_refuses_when_encryption_disabled(photo_dir, encryption_off):
    module = _load_script()
    assert module.main([]) == 2


def test_script_dry_run_reports_without_rewriting(photo_dir, encryption_off, monkeypatch, capsys):
    save("s1", DATA_URL)  # stored as plaintext while the key was off
    monkeypatch.setattr("app.config.BIOMETRIC_ENCRYPTION_KEY", KEY)
    module = _load_script()

    assert module.main([]) == 0
    out = capsys.readouterr().out
    assert '"plaintext": 1' in out
    assert '"rewritten": 0' in out
    # Nothing touched on disk yet.
    assert (photo_dir / "s1.jpg").read_bytes() == b"fake-jpeg-bytes"


def test_script_apply_encrypts_and_is_idempotent(photo_dir, encryption_off, monkeypatch, capsys):
    save("s1", DATA_URL)
    monkeypatch.setattr("app.config.BIOMETRIC_ENCRYPTION_KEY", KEY)
    module = _load_script()

    assert module.main(["--apply"]) == 0
    on_disk = (photo_dir / "s1.jpg").read_bytes()
    assert on_disk[: len(crypto.MAGIC)] == crypto.MAGIC
    assert b"fake-jpeg-bytes" not in on_disk
    assert load("s1.jpg") == b"fake-jpeg-bytes"

    # Re-running must recognise the file as already encrypted.
    capsys.readouterr()
    assert module.main(["--apply"]) == 0
    out = capsys.readouterr().out
    assert '"encrypted": 1' in out
    assert '"rewritten": 0' in out