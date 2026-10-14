from pydantic import BaseModel, Field
from typing import List, Optional


class StudentSync(BaseModel):
    uid: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    roll_no: str = Field(min_length=1, max_length=50)
    image_base64: str = Field(min_length=100, max_length=12_000_000)


class SyncRequest(BaseModel):
    students: List[StudentSync] = Field(min_length=1, max_length=500)


class SyncResponse(BaseModel):
    synced_count: int
    total_in_db: int


class DetectWebcamRequest(BaseModel):
    image_base64: str = Field(min_length=100, max_length=12_000_000)


class VerifyRequest(BaseModel):
    registered_image_base64: str = Field(min_length=100, max_length=12_000_000)
    live_image_base64: str = Field(min_length=100, max_length=12_000_000)


class LivenessVerifyRequest(BaseModel):
    registered_image_base64: str = Field(min_length=100, max_length=12_000_000)
    frames_base64: List[str] = Field(min_length=5, max_length=60)


class VerifyResponse(BaseModel):
    match: bool
    confidence: float
    reason: str
    distance: float
    liveness: Optional[dict] = None


class DetectWebcamResponse(BaseModel):
    faces_detected: int
    frame_width: int
    frame_height: int
    face_data: list


class CCTVDetectResponse(BaseModel):
    faces_detected: int
    face_data: list
    frame_width: int
    frame_height: int
