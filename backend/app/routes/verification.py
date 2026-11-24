from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_db, require_roles
from app.db import Student
from app.models.schemas import LivenessVerifyRequest, VerifyRequest, VerifyResponse
from app.rate_limit import rate_limit_face
from app.services.face_service import MAX_IMAGE_BYTES, face_service
from app.services.liveness_service import liveness_service

router = APIRouter()

MAX_FRAMES = 60

# Blocking model inference runs in FastAPI's threadpool because these handlers
# are plain ``def`` rather than ``async def``.


@router.post("/api/verify")
def verify_student(
    request: VerifyRequest,
    user=Depends(require_roles("admin", "operator")),
    _rate=Depends(rate_limit_face),
):
    """Staff-only 1:1 comparison.

    This accepts two arbitrary client-supplied images, so it is not exposed to
    students. The student flow uses /api/verify_liveness against an enrolled
    template instead of acting as a general face-comparison oracle.
    """
    try:
        registered_bytes = face_service._decode_base64(request.registered_image_base64)
        live_bytes = face_service._decode_base64(request.live_image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.")

    for raw in (registered_bytes, live_bytes):
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image too large (max 8MB).")

    registered_encoding = face_service.get_face_encoding(registered_bytes)
    if registered_encoding is None:
        raise HTTPException(status_code=400, detail="No face detected in the registered image.")

    live_encoding = face_service.get_face_encoding(live_bytes)
    if live_encoding is None:
        raise HTTPException(status_code=400, detail="No face detected in the live image.")

    match, confidence, distance = face_service.verify_faces(registered_encoding, live_encoding)
    if match:
        return VerifyResponse(
            match=True,
            confidence=round(confidence, 2),
            reason="Identity verified successfully.",
            distance=round(distance, 4),
        )
    return VerifyResponse(
        match=False,
        confidence=round(confidence, 2),
        reason="Identity verification failed. Face does not match.",
        distance=round(distance, 4),
    )


@router.post("/api/verify_liveness", response_model=VerifyResponse)
def verify_student_with_liveness(
    request: LivenessVerifyRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    _rate=Depends(rate_limit_face),
):
    # A withdrawn student must not have their biometrics processed on their
    # behalf — fail closed before any inference runs.
    uid = user.get("uid") if isinstance(user, dict) else None
    if uid:
        student = db.scalar(select(Student).where(Student.user_id == uid))
        if student is not None and student.consent_withdrawn_at is not None:
            from app.routes.registry import _iso

            raise HTTPException(
                status_code=409,
                detail={
                    "message": "This student has withdrawn biometric consent; verification is refused.",
                    "withdrawnAt": _iso(student.consent_withdrawn_at),
                },
            )
    try:
        registered_bytes = face_service._decode_base64(request.registered_image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid registered image base64 data.")

    if len(registered_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8MB).")

    registered_encoding = face_service.get_face_encoding(registered_bytes)
    if registered_encoding is None:
        raise HTTPException(status_code=400, detail="No face detected in the registered image.")

    try:
        frames_bytes = [face_service._decode_base64(fb) for fb in request.frames_base64]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid frame base64 data.")

    if len(frames_bytes) < 5:
        raise HTTPException(status_code=400, detail="At least 5 frames are required for liveness detection.")
    if len(frames_bytes) > MAX_FRAMES:
        raise HTTPException(status_code=413, detail="Too many frames (max 60).")
    if any(len(frame) > MAX_IMAGE_BYTES for frame in frames_bytes):
        raise HTTPException(status_code=413, detail="Frame too large (max 8MB).")

    # Derive the true sampling rate from the client's measured interval.
    fps = 1000.0 / request.frame_interval_ms
    liveness_result = liveness_service.detect_liveness(frames_bytes, fps=fps)
    if not liveness_result["live"]:
        return VerifyResponse(
            match=False,
            confidence=0.0,
            reason=f"Liveness check failed (score: {liveness_result['score']}). This may be a photo or video replay.",
            distance=1.0,
            liveness=liveness_result,
        )

    live_encodings = face_service.get_multiple_encodings(frames_bytes)
    if not live_encodings:
        raise HTTPException(status_code=400, detail="No face detected in any live frame.")

    avg_live_encoding = [sum(c) / len(c) for c in zip(*live_encodings)]

    match, confidence, distance = face_service.verify_faces(registered_encoding, avg_live_encoding)
    if match:
        return VerifyResponse(
            match=True,
            confidence=round(confidence, 2),
            reason="Identity verified with liveness (pulse detected).",
            distance=round(distance, 4),
            liveness=liveness_result,
        )
    return VerifyResponse(
        match=False,
        confidence=round(confidence, 2),
        reason="Identity verification failed. Face does not match.",
        distance=round(distance, 4),
        liveness=liveness_result,
    )


@router.get("/api/liveness/challenge")
def issue_liveness_challenge(user=Depends(get_current_user)):
    return liveness_service.issue_challenge()


class ChallengeVerifyRequest(BaseModel):
    token: str
    frames_base64: list[str]
    frame_interval_ms: float = 100.0


@router.post("/api/liveness/verify_challenge")
def verify_liveness_challenge(
    request: ChallengeVerifyRequest,
    user=Depends(get_current_user),
    _rate=Depends(rate_limit_face),
):
    if len(request.frames_base64) < 5:
        raise HTTPException(status_code=400, detail="At least 5 frames are required.")
    frames_bytes = []
    for fb in request.frames_base64:
        try:
            frames_bytes.append(face_service._decode_base64(fb))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid frame base64 data.")
    fps = 1000.0 / request.frame_interval_ms if request.frame_interval_ms else 10.0
    return liveness_service.verify_challenge(frames_bytes, request.token, fps=fps)
