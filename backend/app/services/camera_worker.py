"""Best-effort camera worker health and reconnect tracking.

FaceSnap does not ship an RTSP/ONVIF client (that needs hardware and a
device protocol layer). This module provides the *management* half: per-camera
health, failure counting, and exponential-backoff reconnect scheduling, so a
future worker can plug in without changing the API or the tests.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CameraHealth:
    camera_id: int
    status: str = "offline"  # offline | online | degraded | reconnecting
    last_frame_at: float | None = None
    failures: int = 0
    reconnects: int = 0
    next_retry_at: float | None = None
    last_error: str | None = None


class CameraWorkerManager:
    def __init__(self, base_backoff: float = 1.0, max_backoff: float = 30.0):
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self._health: Dict[int, CameraHealth] = {}

    def register(self, camera_id: int) -> CameraHealth:
        health = self._health.get(camera_id) or CameraHealth(camera_id=camera_id)
        self._health[camera_id] = health
        return health

    def mark_online(self, camera_id: int) -> CameraHealth:
        health = self.register(camera_id)
        health.status = "online"
        health.last_frame_at = time.monotonic()
        health.failures = 0
        health.next_retry_at = None
        health.last_error = None
        return health

    def mark_frame(self, camera_id: int) -> CameraHealth:
        health = self.register(camera_id)
        health.last_frame_at = time.monotonic()
        if health.status != "online":
            health.status = "online"
        return health

    def mark_failure(self, camera_id: int, error: str | None = None) -> CameraHealth:
        health = self.register(camera_id)
        health.failures += 1
        health.last_error = error
        health.status = "degraded" if health.failures < 3 else "reconnecting"
        # Schedule a reconnect with exponential backoff.
        backoff = min(self.max_backoff, self.base_backoff * (2 ** min(health.failures - 1, 6)))
        health.next_retry_at = time.monotonic() + backoff
        health.reconnects += 1
        return health

    def due_for_reconnect(self, camera_id: int, now: float | None = None) -> bool:
        health = self._health.get(camera_id)
        if health is None or health.next_retry_at is None:
            return False
        now = now if now is not None else time.monotonic()
        return now >= health.next_retry_at

    def health(self, camera_id: int) -> CameraHealth | None:
        return self._health.get(camera_id)

    def all_health(self) -> list[CameraHealth]:
        return list(self._health.values())

    def reset(self) -> None:
        self._health.clear()


# In-memory PTZ command queue (per camera). A real driver would consume this.
_ptz_commands: dict[int, list[dict]] = {}


def enqueue_ptz(camera_id: int, command: dict) -> dict:
    _ptz_commands.setdefault(camera_id, []).append(command)
    # Keep the queue bounded.
    if len(_ptz_commands[camera_id]) > 100:
        _ptz_commands[camera_id] = _ptz_commands[camera_id][-100:]
    return {"queued": True, "queueDepth": len(_ptz_commands[camera_id])}


def ptz_queue(camera_id: int) -> list[dict]:
    return list(_ptz_commands.get(camera_id, []))


def clear_ptz_queue(camera_id: int) -> None:
    _ptz_commands.pop(camera_id, None)


# Process-wide singleton. Workers (future) register cameras here.
camera_worker_manager = CameraWorkerManager()
