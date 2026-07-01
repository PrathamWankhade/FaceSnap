import time
import cv2
import numpy as np
import base64
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.camera import pi_camera
from app.services.face_service import face_service

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


@router.get("/api/pi/stream")
def pi_video_feed():
    return StreamingResponse(generate_pi_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/api/pi/capture")
def pi_capture_frame():
    success, frame = pi_camera.read()
    if not success or frame is None:
        raise HTTPException(status_code=503, detail="Pi camera stream unavailable")
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        raise HTTPException(status_code=500, detail="Failed to encode frame")
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return {"image_base64": base64_str}


@router.get("/api/pi/detect")
def pi_detect_faces():
    success, frame = pi_camera.read()
    if not success or frame is None:
        raise HTTPException(status_code=503, detail="Pi camera stream unavailable")

    rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h_img, w_img = rgb_img.shape[:2]
    faces = face_service.detect_faces(rgb_img)

    if not faces:
        return {"faces_detected": 0, "frame_width": w_img, "frame_height": h_img,
                "message": "No faces detected in the current frame."}

    face_data = []
    for (x, y, w, h) in faces:
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w_img, x + w), min(h_img, y + h)
        face_img = rgb_img[y1:y2, x1:x2]
        encodings = face_service.get_embeddings_batch([face_img])
        has_encoding = len(encodings) > 0
        face_data.append({"box": [x, y, w, h], "has_encoding": has_encoding})

    return {"faces_detected": len(faces), "frame_width": w_img, "frame_height": h_img,
            "face_data": face_data, "message": f"Successfully detected {len(faces)} face(s)."}
