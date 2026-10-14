from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS, HOST, PORT
from app.services.camera import pi_camera
from app.services.face_service import face_service
from app.services.vector_service import vector_service
from app.routes.verification import router as verification_router
from app.routes.detection import router as detection_router
from app.routes.pi_routes import router as pi_router

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


@app.on_event("startup")
def startup_event():
    pi_camera.start()
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
    return {
        "message": "Welcome to FaceSnap API (Next-Gen)",
        "engine": "InsightFace ArcFace + Qdrant + rPPG Liveness",
        "students_in_db": vector_service.count() if vector_service.is_ready else -1,
    }


@app.get("/api/health")
def health():
    face_ok = face_service.is_ready
    vec_ok = vector_service.is_ready
    healthy = face_ok and vec_ok
    return {
        "ok": healthy,
        "face_model_ready": face_ok,
        "vector_db_ready": vec_ok,
        "camera": pi_camera.health(),
        "students_in_db": vector_service.count() if vec_ok else 0,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
