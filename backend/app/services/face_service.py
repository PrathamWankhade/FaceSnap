import os
import numpy as np
import cv2
from app.config import ARCFACE_THRESHOLD, DETECTION_CONFIDENCE, EMBEDDING_DIM

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIM = 4096


class FaceService:
    def __init__(self):
        self.app = None
        self._load_model()

    def _load_model(self):
        try:
            import insightface
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

    def count_faces(self, image_bytes) -> int:
        """Number of detected faces, or 0 when the image is unusable."""
        if self.app is None or not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            return 0
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return 0
            h, w = img.shape[:2]
            if h <= 0 or w <= 0 or max(h, w) > MAX_IMAGE_DIM:
                return 0
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return len(self.app.get(rgb_img))
        except Exception:
            return 0

    def get_face_encoding(self, image_bytes):
        if self.app is None:
            return None
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            return None
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            h, w = img.shape[:2]
            if h <= 0 or w <= 0 or max(h, w) > MAX_IMAGE_DIM:
                return None
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
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
                nparr = np.frombuffer(fb, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
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
