from fastapi import APIRouter, Depends, HTTPException
from app.services.face_service import face_service, MAX_IMAGE_BYTES
from app.services.vector_service import vector_service
from app.models.schemas import SyncRequest, SyncResponse, DetectWebcamRequest
from app.models.schemas import DetectWebcamResponse
from app.config import ARCFACE_THRESHOLD
from app.auth import require_roles
from app.rate_limit import rate_limit_face

router = APIRouter()

STAFF = ("admin", "operator")


# Handlers are declared with ``def`` (not ``async def``) on purpose: face
# decoding and model inference are blocking CPU work, so FastAPI runs them in
# its threadpool instead of blocking the event loop.


@router.post("/api/sync", response_model=SyncResponse)
def sync_students(request: SyncRequest, user=Depends(require_roles(*STAFF))):
    if not face_service.is_ready:
        raise HTTPException(status_code=503, detail="Face recognition model not loaded.")
    if len(request.students) > 500:
        raise HTTPException(status_code=413, detail="Too many students in one sync (max 500).")
    synced_count = 0
    for student in request.students:
        try:
            image_bytes = face_service._decode_base64(student.image_base64)
            if len(image_bytes) > MAX_IMAGE_BYTES:
                continue
            encoding = face_service.get_face_encoding(image_bytes)
            if encoding is not None:
                vector_service.upsert(
                    uid=student.uid,
                    embedding=encoding,
                    payload={
                        "uid": student.uid,
                        "name": student.name,
                        "roll_no": student.roll_no,
                    },
                )
                synced_count += 1
        except Exception as e:
            print(f"Sync error for {student.uid}: {e}")
    return SyncResponse(synced_count=synced_count, total_in_db=vector_service.count())


@router.post("/api/detect_webcam", response_model=DetectWebcamResponse)
def detect_webcam(
    request: DetectWebcamRequest,
    user=Depends(require_roles(*STAFF)),
    _rate=Depends(rate_limit_face),
):
    if not face_service.is_ready:
        raise HTTPException(status_code=503, detail="Face recognition model not loaded.")
    try:
        image_bytes = face_service._decode_base64(request.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8MB).")

    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image.")
    h, w = img.shape[:2]
    if max(h, w) > 4096:
        raise HTTPException(status_code=413, detail="Image dimensions too large.")
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    faces = face_service.app.get(rgb_img) if face_service.app else []
    face_data = []
    for face in faces:
        bbox = face.bbox.astype(int).tolist()
        embedding = face.embedding
        norm = np.linalg.norm(embedding)
        normalized = (embedding / norm).tolist() if norm > 0 else embedding.tolist()
        matches = vector_service.search(normalized, limit=1, score_threshold=1.0 - ARCFACE_THRESHOLD)
        match = matches[0] if matches else None
        face_data.append({
            "box": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
            "match": {
                "uid": match["uid"],
                "name": match["name"],
                "roll_no": match["roll_no"],
                "distance": match["distance"],
            } if match else None,
        })

    return DetectWebcamResponse(
        faces_detected=len(faces),
        frame_width=img.shape[1],
        frame_height=img.shape[0],
        face_data=face_data,
    )
