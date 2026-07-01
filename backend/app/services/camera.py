import time
import cv2
import numpy as np
from app.config import PI_CAMERA_ENABLED


class PiCamera:
    def __init__(self):
        self.camera = None
        self.is_running = False

    def start(self):
        if not PI_CAMERA_ENABLED:
            return
        try:
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self.is_running = True
        except Exception as e:
            print(f"Camera init error: {e}")
            self.is_running = False

    def read(self):
        if not self.is_running or self.camera is None:
            return False, None
        return self.camera.read()

    def stop(self):
        if self.camera:
            self.camera.release()
        self.is_running = False


pi_camera = PiCamera()
