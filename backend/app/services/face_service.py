import math
import os

import cv2
import numpy as np

from app.config import (
    ARCFACE_THRESHOLD,
    DETECTION_CONFIDENCE,
    EMBEDDING_DIM,
    LOW_LIGHT_MAX_GAMMA,
    LOW_LIGHT_TARGET_MEAN,
    LOW_LIGHT_THRESHOLD,
)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIM = 4096

CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)


def enhance_low_light(bgr: np.ndarray) -> tuple[np.ndarray, dict]:
    """Lift an under-exposed frame towards a usable luminance range.

    Conditional by design: a frame whose mean luminance is already at/above
    ``LOW_LIGHT_THRESHOLD`` is returned byte-identical, so normal lighting (and
    every embedding enrolled before this step existed) behaves exactly as
    before. A dark frame gets CLAHE on the LAB lightness channel followed by a
    gamma curve that targets ``LOW_LIGHT_TARGET_MEAN``; the gain is capped so a
    near-black frame is not amplified into noise.

    Returns ``(image, metrics)`` where metrics records whether the step ran and
    the luminance before/after — surfaced for logs and tests, never claimed as
    a detection improvement without a measured benchmark.
    """
    if bgr is None or bgr.size == 0:
        raise ValueError("empty image")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    input_mean = float(gray.mean())
    if input_mean >= LOW_LIGHT_THRESHOLD:
        return bgr, {
            "applied": False,
            "input_mean": round(input_mean, 2),
            "output_mean": round(input_mean, 2),
            "gamma": 1.0,
        }

    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    lightness = clahe.apply(lightness)

    current = max(float(lightness.mean()), 1.0)
    target = max(LOW_LIGHT_TARGET_MEAN, current)
    if current < 254.0 and target > current:
        gamma = math.log(current / 255.0) / math.log(target / 255.0)
    else:
        gamma = 1.0
    gamma = float(min(max(gamma, 1.0), LOW_LIGHT_MAX_GAMMA))

    if gamma > 1.0:
        lut = ((np.arange(256, dtype=np.float32) / 255.0) ** (1.0 / gamma)) * 255.0
        lightness = cv2.LUT(lightness, np.clip(lut, 0, 255).astype(np.uint8))

    enhanced = cv2.cvtColor(cv2.merge((lightness, a_channel, b_channel)), cv2.COLOR_LAB2BGR)
    output_mean = float(cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY).mean())
    return enhanced, {
        "applied": True,
        "input_mean": round(input_mean, 2),
        "output_mean": round(output_mean, 2),
        "gamma": round(gamma, 3),
    }



class FaceService:
    def __init__(self):
        self.app = None
        self._load_model()

    def _load_model(self):
        try:
            from insightface.app import FaceAnalysis
            self.app = FaceAnalysis(name='buffalo_s', root=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.insightface'))
            self.app.prepare(ctx_id=0 if self._has_gpu() else -1, det_thresh=DETECTION_CONFIDENCE)
            print(f"InsightFace loaded (device: {'GPU' if self._has_gpu() else 'CPU'})")
        except Exception as e:
            print(f"InsightFace load error: {e}")
            self.app = None

    @staticmethod
    def _has_gpu():
        try:
            import onnxruntime
            return onnxruntime.get_available_providers() and 'CUDAExecutionProvider' in onnxruntime.get_available_providers()
        except Exception:
            return False

    @property
    def is_ready(self):
        return self.app is not None

    @staticmethod
    def _prepare_rgb(image_bytes):
        """Decode, guard, low-light normalise, and convert to RGB.

        Every detection/embedding path goes through this helper so enrollment
        and verification see the same preprocessing.
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        if h <= 0 or w <= 0 or max(h, w) > MAX_IMAGE_DIM:
            return None
        img, _meta = enhance_low_light(img)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def count_faces(self, image_bytes) -> int:
        """Number of detected faces, or 0 when the image is unusable."""
        if self.app is None or not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            return 0
        try:
            rgb_img = self._prepare_rgb(image_bytes)
            if rgb_img is None:
                return 0
            return len(self.app.get(rgb_img))
        except Exception:
            return 0

    def get_face_encoding(self, image_bytes):
        if self.app is None:
            return None
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            return None
        try:
            rgb_img = self._prepare_rgb(image_bytes)
            if rgb_img is None:
                return None
            faces = self.app.get(rgb_img)
            if not faces:
                return None
            if len(faces) > 1:
                # Ambiguous enrollment/verification image: use largest but flag via size order.
                # Callers requiring strict single-face should check face count separately.
                pass
            faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
            embedding = np.asarray(faces[0].embedding, dtype=np.float32)
            if embedding.size != EMBEDDING_DIM:
                return None
            norm = float(np.linalg.norm(embedding))
            if norm <= 0:
                return None
            return (embedding / norm).tolist()
        except Exception as e:
            print(f"Encoding error: {e}")
            return None

    def get_multiple_encodings(self, frames_bytes):
        if self.app is None:
            return []
        results = []
        for fb in frames_bytes:
            try:
                if not fb or len(fb) > MAX_IMAGE_BYTES:
                    continue
                rgb_img = self._prepare_rgb(fb)
                if rgb_img is None:
                    continue
                faces = self.app.get(rgb_img)
                if not faces:
                    continue
                faces.sort(key=lambda f: f.bbox[2] * f.bbox[3], reverse=True)
                embedding = faces[0].embedding
                norm = np.linalg.norm(embedding)
                results.append((embedding / norm).tolist() if norm > 0 else embedding.tolist())
            except Exception:
                continue
        return results

    def verify_faces(self, registered_encoding, live_encoding):
        try:
            reg = np.asarray(registered_encoding, dtype=np.float32).reshape(-1)
            live = np.asarray(live_encoding, dtype=np.float32).reshape(-1)
        except Exception:
            return False, 0.0, 1.0
        if reg.shape != live.shape or reg.size != EMBEDDING_DIM:
            return False, 0.0, 1.0
        reg_norm = float(np.linalg.norm(reg))
        live_norm = float(np.linalg.norm(live))
        if reg_norm <= 0 or live_norm <= 0:
            return False, 0.0, 1.0
        cos_sim = float(np.dot(reg, live) / (reg_norm * live_norm + 1e-10))
        cos_sim = max(-1.0, min(1.0, cos_sim))
        distance = float(1 - cos_sim)
        # Clamp float32 rounding noise to exact zero; far below ARCFACE_THRESHOLD so matching is unaffected.
        if distance < 1e-9:
            distance = 0.0
        if distance < ARCFACE_THRESHOLD:
            # Uncalibrated similarity score (not a probability). Higher = more similar.
            similarity = max(0.0, min(100.0, 100.0 - (distance * 100.0 / ARCFACE_THRESHOLD * 0.5)))
            return True, similarity, distance
        return False, max(0.0, 100.0 - (distance * 100.0)), distance

    @staticmethod
    def _decode_base64(base64_string):
        import base64
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        return base64.b64decode(base64_string)


face_service = FaceService()
