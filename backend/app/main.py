from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    APP_ENV,
    CORS_ORIGINS,
    HOST,
    IS_PRODUCTION,
    PORT,
    REQUIRE_AUTH,
)
from app.db import SessionLocal, init_db
from app.services.camera import pi_camera
from app.services.face_service import face_service
from app.services.vector_service import vector_service
from app.routes.verification import router as verification_router
from app.routes.detection import router as detection_router
from app.routes.pi_routes import router as pi_router
from app.routes.registry import router as registry_router

app = FastAPI(title="FaceSnap API - Next Gen")

# Bearer tokens are sent in headers, not cookies, so credentials are not needed.
# A wildcard origin is also invalid together with allow_credentials=True.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(verification_router)
app.include_router(detection_router)
app.include_router(pi_router)
app.include_router(registry_router)


def _validate_runtime(
    app_env: str = APP_ENV,
    require_auth: bool = REQUIRE_AUTH,
    cors_origins: list[str] = CORS_ORIGINS,
) -> None:
    """Fail fast on unsafe production configuration.

    Development keeps the convenient auth bypass, but it must be a deliberate
    local-only choice. Production refuses to boot with the bypass enabled or
    with a wildcard CORS policy.
    """
    if app_env == "production":
        if not require_auth:
            raise RuntimeError(
                "Refusing to start: REQUIRE_AUTH must be true when APP_ENV=production."
            )
        if not cors_origins or "*" in cors_origins:
            raise RuntimeError(
                "Refusing to start: set CORS_ORIGINS to the deployed frontend origin(s) "
                "when APP_ENV=production."
            )
        return

    if not require_auth:
        print("=" * 72)
        print("DEVELOPMENT AUTH BYPASS ENABLED (REQUIRE_AUTH=false)")
        print("Every request is treated as a local admin. Never expose this server")
        print("to a network. Set APP_ENV=production and REQUIRE_AUTH=true to enforce")
        print("Firebase ID tokens.")
        print("=" * 72)


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
    _validate_runtime()
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
        "environment": APP_ENV,
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
        "environment": APP_ENV,
        "auth_required": REQUIRE_AUTH,
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
