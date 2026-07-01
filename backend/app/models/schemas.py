from pydantic import BaseModel
from typing import List, Optional

class StudentSync(BaseModel):
    uid: str
    name: str
    roll_no: str
    image_base64: str

class SyncRequest(BaseModel):
    students: List[StudentSync]

class DetectWebcamRequest(BaseModel):
    image_base64: str

class VerifyRequest(BaseModel):
    registered_image_base64: str
    live_image_base64: str
