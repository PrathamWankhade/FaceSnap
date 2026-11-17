from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.config import ARCFACE_THRESHOLD, REVIEW_QUEUE_ENABLED
from app.db import DetectionReview, User, get_db, utcnow
from app.models.schemas import (
    DetectWebcamRequest,
    DetectWebcamResponse,
    SyncRequest,
    SyncResponse,
)
from app.rate_limit import rate_limit_face
from app.services.face_service import MAX_IMAGE_BYTES, face_service
from app.services.vector_service import vector_service
from app.metrics import metrics

router = APIRouter()

STAFF = ("admin", "operator")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ReviewResolveRequest(BaseModel):
    status: str = "resolved"
    note: str | None = None


def _review_dict(row: DetectionReview) -> dict:
    return {
        "id": row.id,
        "detectedAt": row.detected_at.isoformat() + "Z" if row.detected_at else None,
        "status": row.status,
        "cameraId": row.camera_id,
        "nearestUid": row.nearest_uid,
        "nearestDistance": row.nearest_distance,
        "note": row.note,
        "resolvedBy": row.resolved_by,
        "resolvedAt": row.resolved_at.isoformat() + "Z" if row.resolved_at else None,
    }


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
    db: Session = Depends(get_db),
):
    if not face_service.is_ready:
        raise HTTPException(status_code=503, detail="Face recognition model not loaded.")
    try:
        image_bytes = face_service._decode_base64(request.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8MB).")

    import cv2
    import numpy as np

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
        if match is not None:
            try:
                metrics.record_match_distance(match["distance"], route="/api/detect_webcam")
            except Exception:
                pass
        face_data.append({
            "box": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
            "match": {
                "uid": match["uid"],
                "name": match["name"],
                "roll_no": match["roll_no"],
                "distance": match["distance"],
            } if match else None,
        })

        # Persist unmatched detections for later review (no biometric image stored).
        if match is None and REVIEW_QUEUE_ENABLED:
            try:
                nearest = None
                # vector_service.search with a loose threshold to capture nearest candidate
                loose = vector_service.search(normalized, limit=1, score_threshold=0.0)
                if loose:
                    nearest = loose[0]
                review = DetectionReview(
                    camera_id=None,
                    status="pending",
                    nearest_uid=nearest["uid"] if nearest else None,
                    nearest_distance=nearest["distance"] if nearest else None,
                    created_by=getattr(user, "id", None) if not isinstance(user, dict) else user.get("uid"),
                )
                db.add(review)
                db.commit()
            except Exception:
                db.rollback()

    return DetectWebcamResponse(
        faces_detected=len(faces),
        frame_width=img.shape[1],
        frame_height=img.shape[0],
        face_data=face_data,
    )


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------
@router.get("/api/detections/review")
def list_review_items(
    user: User = Depends(require_roles(*STAFF)),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=500),
):
    stmt = select(DetectionReview).order_by(DetectionReview.detected_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(DetectionReview.status == status)
    rows = db.scalars(stmt).all()
    return {"items": [_review_dict(r) for r in rows], "total": len(rows)}


@router.patch("/api/detections/review/{item_id}")
def resolve_review_item(
    item_id: int,
    payload: ReviewResolveRequest,
    user: User = Depends(require_roles(*STAFF)),
    db: Session = Depends(get_db),
):
    row = db.get(DetectionReview, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Review item not found.")
    if payload.status not in {"pending", "resolved", "dismissed"}:
        raise HTTPException(status_code=422, detail="Invalid status.")
    row.status = payload.status
    row.note = payload.note if payload.note is not None else row.note
    if payload.status in {"resolved", "dismissed"}:
        row.resolved_by = user.id if hasattr(user, "id") else getattr(user, "uid", None)
        row.resolved_at = utcnow()
    db.commit()
    db.refresh(row)
    # audit
    try:
        from app.routes.registry import _audit
        _audit(db, user, "detection.review.resolve", "detection_review", row.id)
        db.commit()
    except Exception:
        pass
    return _review_dict(row)