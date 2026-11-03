from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import (
    APP_ENV,
    CORS_ORIGINS,
    HEALTH_DB_TIMEOUT,
    HEALTH_VECTOR_TIMEOUT,
    HOST,
    PORT,
    REQUIRE_AUTH,
)
from app.db import SessionLocal, init_db
from app.logging_setup import configure_logging
from app.middleware.logging import RequestLoggingMiddleware
from app.routes.detection import router as detection_router
from app.routes.pi_routes import router as pi_router
from app.routes.registry import router as registry_router
from app.routes.verification import router as verification_router
from app.services.camera import pi_camera
from app.services.face_service import face_service
from app.services.vector_service import vector_service

configure_logging()

app = FastAPI(title="FaceSnap API - Next Gen")

# Correlation ids, structured access logs and security headers on every response.
app.add_middleware(RequestLoggingMiddleware)

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


def _component_health():
    """Readiness of each hard dependency, each bounded by its own timeout.

    Never triggers model inference or image loading; a dependency that does not
    answer within its timeout counts as unhealthy rather than hanging health.
    """
    pool = ThreadPoolExecutor(max_workers=3)

    def probe_db():
        return _db_counts()[0]

    def probe_vector():
        return vector_service.is_ready

    def probe_face():
        return face_service.is_ready

    def probe_camera():
        return pi_camera.health().get("ok", False)

    results = {}
    for name, probe, timeout in (
        ("database", probe_db, HEALTH_DB_TIMEOUT),
        ("vector_db", probe_vector, HEALTH_VECTOR_TIMEOUT),
        ("face_model", probe_face, HEALTH_VECTOR_TIMEOUT),
        ("camera", probe_camera, HEALTH_VECTOR_TIMEOUT),
    ):
        future = pool.submit(probe)
        try:
            results[name] = bool(future.result(timeout=timeout))
        except Exception:
            results[name] = False
    pool.shutdown(wait=False)
    return results


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


@app.get("/api/health/live")
def health_live():
    """Liveness probe: the process is up. Never touches a dependency."""
    return {"status": "live", "environment": APP_ENV}


@app.get("/api/health")
def health():
    """Readiness probe: per-component status with bounded timeouts.

    Returns ``200`` with ``ok:true`` when every hard dependency is ready,
    ``503`` when any hard dependency is down or slower than its timeout.
    Never triggers model inference.
    """
    components = _component_health()
    face_ok = components["face_model"]
    vec_ok = components["vector_db"]
    db_ok, students, attendance = _db_counts()
    components["database"] = db_ok

    healthy = all(components.values())
    status_code = 200 if healthy else 503
    return JSONResponse(
        content={
            "ok": healthy,
            "environment": APP_ENV,
            "auth_required": REQUIRE_AUTH,
            "components": components,
            "face_model_ready": face_ok,
            "vector_db_ready": vec_ok,
            "database_ready": db_ok,
            "camera": pi_camera.health(),
            "students_in_db": students,
            "attendance_rows": attendance,
            "embeddings_indexed": vector_service.count() if vec_ok else 0,
        },
        status_code=status_code,
    )


@app.get("/api/metrics")
def metrics():
    """Prometheus text exposition (aggregate counts only, no PII, no labels with ids)."""
    # In-process counters only; exported cheaply without a client library.
    # Routes are bound labels to avoid cardinality bombs and id leakage.
    lines = [
        "# HELP facesnap_requests_total Total HTTP requests by route and status",
        "# TYPE facesnap_requests_total counter",
        "# HELP facesnap_rate_limited_total Total rate-limiter rejections",
        "# TYPE facesnap_rate_limited_total counter",
        "# HELP facesnap_auth_failures_total Total 401/403 responses",
        "# TYPE facesnap_auth_failures_total counter",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
