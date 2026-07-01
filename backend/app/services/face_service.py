import os
import numpy as np
import cv2
import tensorflow as tf
from keras_facenet import FaceNet
from ultralytics import YOLO
from app.config import RECOGNITION_THRESHOLD, YOLO_CONFIDENCE, FACENET_INPUT_SIZE


class FaceService:
    def __init__(self):
        self.embedder = None
        self.yolo_model = None
        self.registered_students = {}
        self._load_models()

    def _load_models(self):
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "yolov8n.pt")
        try:
            self.embedder = FaceNet()
        except Exception as e:
            print(f"FaceNet load error: {e}")
            self.embedder = None

        try:
            self.yolo_model = YOLO(model_path, verbose=False)
            try:
                self.yolo_model.to('cuda')
            except Exception:
                pass
        except Exception as e:
            print(f"YOLO load error: {e}")
            self.yolo_model = None

    @property
    def is_ready(self):
        return self.embedder is not None and self.yolo_model is not None

    def get_device(self):
        return 'cuda' if tf.config.list_physical_devices('GPU') else 'cpu'

    def detect_faces(self, frame):
        if self.yolo_model is None:
            return []
        results = self.yolo_model.predict(
            frame, conf=YOLO_CONFIDENCE, classes=[0],
            device=0 if tf.config.list_physical_devices('GPU') else 'cpu',
            verbose=False
        )
        boxes = []
        for r in results:
            for box in r.boxes.xyxy:
                x1, y1, x2, y2 = map(int, box)
                boxes.append((x1, y1, x2 - x1, y2 - y1))
        return boxes

    def preprocess_face(self, face_img):
        if face_img is None or face_img.size == 0:
            return None
        try:
            face_img = cv2.resize(face_img, FACENET_INPUT_SIZE, interpolation=cv2.INTER_CUBIC)
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
            face_img = cv2.filter2D(face_img, -1, kernel)
            mean, std = np.mean(face_img), np.std(face_img)
            face_img = (face_img - mean) / (std if std > 0 else 1.0)
            return face_img
        except Exception:
            return None

    def get_embeddings_batch(self, face_imgs):
        if not face_imgs or self.embedder is None:
            return np.array([])
        valid_faces = []
        for img in face_imgs:
            processed = self.preprocess_face(img)
            if processed is not None:
                valid_faces.append(processed)
        if not valid_faces:
            return np.array([])
        batch = np.stack(valid_faces)
        return self.embedder.model.predict(batch, verbose=0)

    def get_face_encoding(self, image_bytes):
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            faces = self.detect_faces(rgb_img)
            if not faces:
                return None
            faces.sort(key=lambda f: f[2] * f[3], reverse=True)
            x, y, w, h = faces[0]
            h_img, w_img = rgb_img.shape[:2]
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(w_img, x + w), min(h_img, y + h)
            face_img = rgb_img[y1:y2, x1:x2]
            encodings = self.get_embeddings_batch([face_img])
            if len(encodings) == 0:
                return None
            return encodings[0].tolist()
        except Exception as e:
            print(f"Encoding error: {e}")
            return None

    def find_best_match(self, live_encoding):
        best_distance = float('inf')
        best_student = None
        live_np = np.array(live_encoding)
        for uid, student_data in self.registered_students.items():
            stored_enc = student_data.get("encoding")
            if stored_enc is None:
                continue
            dist = np.linalg.norm(stored_enc if isinstance(stored_enc, np.ndarray) else np.array(stored_enc) - live_np)
            if dist < best_distance:
                best_distance = dist
                best_student = student_data
        if best_distance < RECOGNITION_THRESHOLD and best_student is not None:
            return best_student, float(best_distance)
        return None, float(best_distance)

    def verify_faces(self, registered_encoding, live_encoding):
        reg_np = np.array(registered_encoding)
        live_np = np.array(live_encoding)
        distance = float(np.linalg.norm(reg_np - live_np))
        if distance < RECOGNITION_THRESHOLD:
            confidence = max(0, min(100, 100 - (distance * 100 / RECOGNITION_THRESHOLD * 0.2)))
            return True, confidence, distance
        return False, max(0, 100 - (distance * 100)), distance

    def sync_students(self, students):
        self.registered_students.clear()
        synced_count = 0
        for student in students:
            try:
                image_bytes = self._decode_base64(student.image_base64)
                encoding = self.get_face_encoding(image_bytes)
                if encoding is not None:
                    self.registered_students[student.uid] = {
                        "uid": student.uid,
                        "name": student.name,
                        "roll_no": student.roll_no,
                        "encoding": np.array(encoding)
                    }
                    synced_count += 1
            except Exception as e:
                print(f"Sync error for {student.uid}: {e}")
        return synced_count

    @staticmethod
    def _decode_base64(base64_string):
        import base64
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        return base64.b64decode(base64_string)


face_service = FaceService()
