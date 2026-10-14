from fastapi import APIRouter, Depends, HTTPException
from app.services.face_service import face_service, MAX_IMAGE_BYTES
from app.services.vector_service import vector_service
from app.services.liveness_service import liveness_service
from app.models.schemas import VerifyRequest, LivenessVerifyRequest, VerifyResponse
from app.auth import get_current_user

router = APIRouter()

MAX_FRAMES = 60


@router.post("/api/verify")
async def verify_student(request: VerifyRequest, user=Depends(get_current_user)):
    try:
        registered_bytes = face_service._decode_base64(request.registered_image_base64)
        live_bytes = face_service._decode_base64(request.live_image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.")

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
async def verify_student_with_liveness(request: LivenessVerifyRequest, user=Depends(get_current_user)):
    try:
        registered_bytes = face_service._decode_base64(request.registered_image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid registered image base64 data.")

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

    liveness_result = liveness_service.detect_liveness(frames_bytes)
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
            reason=f"Identity verified with liveness (pulse detected).",
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
