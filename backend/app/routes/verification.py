from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.services.face_service import face_service
from app.models.schemas import VerifyRequest

router = APIRouter()


@router.post("/api/register")
async def register_student(
    name: str = Form(...),
    roll_no: str = Form(...),
    department: str = Form("Information Technology"),
    year: str = Form(...),
    semester: str = Form(...),
    image: UploadFile = File(...)
):
    image_bytes = await image.read()
    encoding = face_service.get_face_encoding(image_bytes)
    if encoding is None:
        raise HTTPException(status_code=400, detail="No face detected in the provided image.")
    student_id = f"{roll_no}_{name}"
    face_service.registered_students[student_id] = {
        "name": name,
        "roll_no": roll_no,
        "department": department,
        "year": year,
        "semester": semester,
        "encoding": encoding
    }
    return {"message": "Student registered successfully", "student_id": student_id}


@router.post("/api/verify")
async def verify_student(request: VerifyRequest):
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
        return {
            "match": True,
            "confidence": float(confidence),
            "reason": "Identity verified successfully.",
            "distance": float(distance)
        }
    return {
        "match": False,
        "confidence": float(confidence),
        "reason": "Identity verification failed. Face does not match.",
        "distance": float(distance)
    }
