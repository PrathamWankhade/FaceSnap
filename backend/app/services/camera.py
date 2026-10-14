import time
import cv2
import numpy as np
from app.config import PI_CAMERA_ENABLED


class PiCamera:
    def __init__(self):
        self.camera = None
        self.is_running = False
        self.last_error: str | None = None

    def start(self):
        if not PI_CAMERA_ENABLED:
            self.last_error = "PI_CAMERA_ENABLED is not true"
            return
        try:
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            if not self.camera.isOpened():
                self.last_error = "VideoCapture failed to open device 0"
                self.camera = None
                self.is_running = False
                return
            self.is_running = True
            self.last_error = None
        except Exception as e:
            print(f"Camera init error: {e}")
            self.last_error = str(e)
            self.is_running = False

    def health(self):
        return {
            "enabled": PI_CAMERA_ENABLED,
            "running": self.is_running,
            "opened": bool(self.camera is not None and self.camera.isOpened()),
            "last_error": self.last_error,
        }

    def read(self):
        if not self.is_running or self.camera is None:
            return False, None
        return self.camera.read()

    def stop(self):
        if self.camera:
            self.camera.release()
        self.is_running = False


pi_camera = PiCamera()
