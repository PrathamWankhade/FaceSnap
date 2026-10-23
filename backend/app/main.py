from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS, HOST, PORT
from app.db import SessionLocal, init_db
from app.services.camera import pi_camera
from app.services.face_service import face_service
from app.services.vector_service import vector_service
from app.routes.verification import router as verification_router
from app.routes.detection import router as detection_router
from app.routes.pi_routes import router as pi_router
from app.routes.registry import router as registry_router

app = FastAPI(title="FaceSnap API - Next Gen")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(verification_router)
app.include_router(detection_router)
app.include_router(pi_router)
app.include_router(registry_router)


def _db_counts():
    """Cheap database probe used by / and /api/health."""
    try:
        from sqlalchemy import func, select

        from app.db import Attendance, Student

        with SessionLocal() as db:
            students = db.scalar(select(func.count()).select_from(Student)) or 0
            attendance = db.scalar(select(func.count()).select_from(Attendance)) or 0
        return True, students, attendance
    except Exception:
        return False, 0, 0


@app.on_event("startup")
def startup_event():
    init_db()
    pi_camera.start()
    db_ok, students, attendance = _db_counts()
    print(f"Database ready: {db_ok} ({students} students, {attendance} attendance rows).")
    if vector_service.is_ready:
        print(f"Vector DB ready with {vector_service.count()} existing entries.")
    else:
        print("Vector DB not available.")
    if not face_service.is_ready:
        print("WARNING: Face recognition model not loaded. Some endpoints will fail.")


@app.on_event("shutdown")
def shutdown_event():
    pi_camera.stop()


@app.get("/")
def read_root():
    db_ok, students, _ = _db_counts()
    return {
        "message": "Welcome to FaceSnap API (Next-Gen)",
        "engine": "InsightFace ArcFace + Qdrant + rPPG Liveness",
        "database_ready": db_ok,
        "students_in_db": students,
        "embeddings_indexed": vector_service.count() if vector_service.is_ready else -1,
    }


@app.get("/api/health")
def health():
    face_ok = face_service.is_ready
    vec_ok = vector_service.is_ready
    db_ok, students, attendance = _db_counts()
    healthy = face_ok and vec_ok and db_ok
    return {
        "ok": healthy,
        "face_model_ready": face_ok,
        "vector_db_ready": vec_ok,
        "database_ready": db_ok,
        "camera": pi_camera.health(),
        "students_in_db": students,
        "attendance_rows": attendance,
        "embeddings_indexed": vector_service.count() if vec_ok else 0,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
