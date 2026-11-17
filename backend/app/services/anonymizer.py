"""Best-effort privacy-preserving anonymization.

Optional blurring of face regions in exported images. Off by default
(``ANONYMIZE_EXPORTS``). This is a convenience, not a guarantee: it does not
remove identifying information from metadata or other fields.
"""
from __future__ import annotations

import cv2
import numpy as np


def blur_regions(image_bytes: bytes, boxes: list[tuple[int, int, int, int]], kernel: int = 31) -> bytes:
    """Blur the given (x, y, w, h) regions in a JPEG/PNG image.

    Returns the re-encoded JPEG bytes. If decoding fails, returns the input
    unchanged.
    """
    if not boxes:
        return image_bytes
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes
    h, w = img.shape[:2]
    for (x, y, bw, bh) in boxes:
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(w, int(x) + int(bw))
        y2 = min(h, int(y) + int(bh))
        if x2 <= x1 or y2 <= y1:
            continue
        roi = img[y1:y2, x1:x2]
        k = kernel if kernel % 2 == 1 else kernel + 1
        img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
    ok, buf = cv2.imencode(".jpg", img)
    if not ok:
        return image_bytes
    return buf.tobytes()