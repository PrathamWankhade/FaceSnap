"""Rate limiting for expensive face endpoints.

Two backends behind one dependency:

* ``memory`` (default) — a per-process sliding window. Correct for a single
  worker; a multi-worker deployment would enforce ``limit * workers``.
* ``redis`` — a shared fixed-window counter (INCR + EXPIRE) so every worker
  enforces the same budget. A fixed window can burst at a minute boundary; that
  is an accepted trade for a face-matching limiter, not a billing meter.

If Redis is configured but unreachable, the limiter falls back to the local
window and logs a throttled warning: an availability problem must not turn into
an open door, and it must not take the attendance flow down either. This is a
best-effort abuse control, not a security boundary.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import (
    RATE_LIMIT_BACKEND,
    RATE_LIMIT_PER_MINUTE,
    REDIS_URL,
    TRUST_PROXY_HEADERS,
)

logger = logging.getLogger("facesnap.rate_limit")

WINDOW_SECONDS = 60.0
# How often a Redis outage may produce a log line (seconds).
_FALLBACK_LOG_INTERVAL = 60.0


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


class RedisLimiter:
    """Shared fixed-window limiter; falls back to a local window on Redis errors."""

    def __init__(self, limit: int, url: str = REDIS_URL, client=None):
        self.limit = limit
        self.url = url
        self._client = client
        self._fallback = SlidingWindowLimiter(limit)
        self._last_warning = 0.0
        self._lock = threading.Lock()

    def _redis(self):
        if self._client is not None:
            return self._client
        import redis  # imported lazily so the memory backend needs no dependency

        self._client = redis.Redis.from_url(
            self.url,
            socket_timeout=0.25,
            socket_connect_timeout=0.25,
            decode_responses=True,
        )
        return self._client

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        window = int(time.time() // WINDOW_SECONDS)
        redis_key = f"facesnap:ratelimit:{key}:{window}"
        try:
            client = self._redis()
            pipe = client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, int(WINDOW_SECONDS) + 5)
            count = int(pipe.execute()[0])
            return count <= self.limit
        except Exception as exc:  # noqa: BLE001 - any Redis failure falls back
            now = time.monotonic()
            with self._lock:
                should_log = now - self._last_warning > _FALLBACK_LOG_INTERVAL
                if should_log:
                    self._last_warning = now
            if should_log:
                logger.warning(
                    "Redis rate-limit store unavailable (%s); using the per-process window.",
                    exc.__class__.__name__,
                )
            return self._fallback.allow(key)

    def reset(self) -> None:
        self._fallback.reset()


def _build_limiter():
    if RATE_LIMIT_BACKEND == "redis":
        logger.info("Rate limiter backend: redis (%s)", REDIS_URL)
        return RedisLimiter(RATE_LIMIT_PER_MINUTE)
    if RATE_LIMIT_BACKEND not in {"memory", ""}:
        logger.warning("Unknown RATE_LIMIT_BACKEND=%r; using the memory limiter.", RATE_LIMIT_BACKEND)
    return SlidingWindowLimiter(RATE_LIMIT_PER_MINUTE)


_limiter = _build_limiter()


def _client_key(request: Request) -> str:
    # X-Forwarded-For is client-controlled unless a trusted proxy overwrites it.
    # Trusting it unconditionally would let anyone bypass the limiter.
    if TRUST_PROXY_HEADERS:
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
            headers={"Retry-After": str(int(WINDOW_SECONDS))},
        )
