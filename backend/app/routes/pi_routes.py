import time
import cv2
import numpy as np
import base64
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.services.camera import pi_camera
from app.services.face_service import face_service
from app.services.vector_service import vector_service
from app.config import ARCFACE_THRESHOLD
from app.auth import require_camera_caller

router = APIRouter()


def generate_pi_frames():
    while True:
        success, frame = pi_camera.read()
        if not success or frame is None:
            time.sleep(0.1)
            continue
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.03)


@router.get("/api/pi/health")
def pi_health(_=Depends(require_camera_caller)):
    return {
        "camera": pi_camera.health(),
        "face_model_ready": face_service.is_ready,
        "vector_db_ready": vector_service.is_ready,
    }


@router.get("/api/pi/stream")
def pi_video_feed(_=Depends(require_camera_caller)):
    return StreamingResponse(generate_pi_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/api/pi/capture")
def pi_capture_frame(_=Depends(require_camera_caller)):
    success, frame = pi_camera.read()
    if not success or frame is None:
        raise HTTPException(status_code=503, detail="Pi camera stream unavailable")
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        raise HTTPException(status_code=500, detail="Failed to encode frame")
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return {"image_base64": base64_str}


@router.get("/api/pi/detect")
def pi_detect_faces(_=Depends(require_camera_caller)):
    """Real recognition: detect faces in the Pi frame and match against enrolled embeddings.

    Never fabricates an identity. Unknown faces return match=None.
    """
    if not face_service.is_ready:
        raise HTTPException(status_code=503, detail="Face recognition model not loaded.")
    success, frame = pi_camera.read()
    if not success or frame is None:
        raise HTTPException(status_code=503, detail="Pi camera stream unavailable")

    rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h_img, w_img = rgb_img.shape[:2]
    faces = face_service.app.get(rgb_img) if face_service.app else []

    if not faces:
        return {"faces_detected": 0, "frame_width": w_img, "frame_height": h_img,
                "face_data": [], "message": "No faces detected in the current frame."}

    face_data = []
    for face in faces:
        bbox = face.bbox.astype(int).tolist()
        x1, y1, x2, y2 = max(0, bbox[0]), max(0, bbox[1]), min(w_img, bbox[2]), min(h_img, bbox[3])
        embedding = np.asarray(face.embedding, dtype=np.float32)
        norm = float(np.linalg.norm(embedding))
        if norm <= 0:
            face_data.append({"box": [x1, y1, x2 - x1, y2 - y1], "has_encoding": False, "match": None})
            continue
        normalized = (embedding / norm).tolist()
        matches = vector_service.search(normalized, limit=1, score_threshold=1.0 - ARCFACE_THRESHOLD)
        match = matches[0] if matches else None
        face_data.append({
            "box": [x1, y1, x2 - x1, y2 - y1],
            "has_encoding": True,
            "match": {
                "uid": match["uid"],
                "name": match["name"],
                "roll_no": match["roll_no"],
                "distance": match["distance"],
            } if match else None,
        })

    return {"faces_detected": len(faces), "frame_width": w_img, "frame_height": h_img,
            "face_data": face_data, "message": f"Successfully detected {len(faces)} face(s)."}
