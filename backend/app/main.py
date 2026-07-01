from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS, HOST, PORT
from app.services.camera import pi_camera
from app.routes.verification import router as verification_router
from app.routes.detection import router as detection_router
from app.routes.pi_routes import router as pi_router

app = FastAPI(title="FaceSnap API")

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


@app.on_event("shutdown")
def shutdown_event():
    pi_camera.stop()


@app.get("/")
def read_root():
    return {"message": "Welcome to FaceSnap API (NVIDIA Face AI System)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
