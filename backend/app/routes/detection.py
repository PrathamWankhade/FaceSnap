import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from app.services.face_service import face_service
from app.models.schemas import SyncRequest, DetectWebcamRequest

router = APIRouter()


@router.post("/api/sync")
async def sync_students(request: SyncRequest):
    synced_count = face_service.sync_students(request.students)
    return {"message": f"Successfully synced {synced_count} students.", "synced_count": synced_count}


@router.post("/api/detect_webcam")
async def detect_webcam(request: DetectWebcamRequest):
    try:
        image_bytes = face_service._decode_base64(request.image_base64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")

    h_img, w_img = rgb_img.shape[:2]
    faces = face_service.detect_faces(rgb_img)

    if not faces:
        return {"faces_detected": 0, "frame_width": w_img, "frame_height": h_img, "face_data": []}

    face_data = []
    for (x, y, w, h) in faces:
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w_img, x + w), min(h_img, y + h)
        face_img = rgb_img[y1:y2, x1:x2]
        encodings = face_service.get_embeddings_batch([face_img])

        match = None
        if len(encodings) > 0:
            best_student, best_distance = face_service.find_best_match(encodings[0])
            if best_student is not None:
                match = {
                    "uid": best_student["uid"],
                    "name": best_student["name"],
                    "roll_no": best_student["roll_no"],
                    "distance": best_distance
                }

        face_data.append({"box": [x, y, w, h], "match": match})

    return {"faces_detected": len(faces), "frame_width": w_img, "frame_height": h_img, "face_data": face_data}
