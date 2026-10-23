"""In-process rate limiting for expensive face endpoints.

A single-process sliding window is enough for a small deployment and keeps the
project dependency-free. For multi-worker deployments, move this to Redis (the
interface is intentionally tiny).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import RATE_LIMIT_PER_MINUTE

WINDOW_SECONDS = 60.0


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = WINDOW_SECONDS):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter = SlidingWindowLimiter(RATE_LIMIT_PER_MINUTE)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_face(request: Request) -> None:
    """FastAPI dependency applied to the face-matching/verification routes."""
    if not _limiter.allow(_client_key(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many face requests. Please wait a moment and try again.",
        )
