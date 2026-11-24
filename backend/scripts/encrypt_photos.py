#!/usr/bin/env python
"""Encrypt existing enrollment photos in place (dry run by default).

Photos saved before ``BIOMETRIC_ENCRYPTION_KEY`` was configured are stored
as plaintext JPEG. This script rewrites each photo through the encrypted
store path (read via ``image_store.load``, write via ``save_bytes``), so the
plaintext originals are never exposed and each file gets a fresh nonce.

    python scripts/encrypt_photos.py            # report only
    python scripts/encrypt_photos.py --apply    # rewrite encrypted

Refuses to run when encryption is disabled (no key): there is nothing to do,
and rewriting without a key would be a silent no-op.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually rewrite files; without this flag the script only reports",
    )
    args = parser.parse_args(argv)

    from app.config import FACE_IMAGE_DIR
    from app.services.biometric_crypto import is_enabled, is_encrypted
    from app.services.image_store import list_keys, save_bytes

    if not is_enabled():
        print(
            "Encryption is disabled (BIOMETRIC_ENCRYPTION_KEY unset). "
            "Configure a key first; refusing to rewrite files as a no-op.",
            file=sys.stderr,
        )
        return 2

    root = Path(FACE_IMAGE_DIR)
    keys = list_keys(root)
    summary = {
        "dry_run": not args.apply,
        "directory": str(root),
        "total": len(keys),
        "encrypted": 0,
        "plaintext": 0,
        "rewritten": 0,
    }
    for key in keys:
        path = root / key
        raw = path.read_bytes()
        if is_encrypted(raw):
            summary["encrypted"] += 1
            continue
        summary["plaintext"] += 1
        if args.apply:
            student_id = path.stem
            save_bytes(student_id, raw)
            summary["rewritten"] += 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["dry_run"] and summary["plaintext"]:
        print(
            "\nDry run: nothing rewritten. Re-run with --apply to encrypt.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())