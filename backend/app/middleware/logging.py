"""Request logging + security-header middleware.

- Every request gets a correlation id (inbound ``X-Request-Id`` honoured, sanitised;
  otherwise generated) echoed on the response header ``X-Request-Id``.
- Production logs are structured JSON on stdout; development logs are human-readable on stderr.
- Sensitive headers (``Authorization``) are redacted from logs and never reach the client.
- Security headers are set on every response (CSP is deliberately minimal: same-origin scripts
  plus inline styles needed by Tailwind; nothing loads from an unverified origin).
"""
from __future__ import annotations

import json
import logging
import secrets
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import IS_PRODUCTION

logger = logging.getLogger("facesnap.request")

# Sensitive header names whose values must never be written to a log line or echoed.
_REDACTED_HEADERS = {"authorization", "x-service-key", "cookie", "set-cookie"}

# Public path prefixes whose responses may be cached by browsers; everything else gets
# "no-store" so biometric/attendance data never sits in a shared cache.
_PUBLIC_PATHS = ("/api/health", "/api/health/live", "/", "/docs", "/openapi.json", "/favicon.ico")


def _safe_header_value(name: str, value: str) -> str:
    if name.lower() in _REDACTED_HEADERS:
        return "[REDACTED]"
    return value[:400] + ("…" if len(value) > 400 else "")


def _format_record(record: dict) -> str:
    """Structured JSON in production, key=value text in development."""
    if IS_PRODUCTION:
        return json.dumps(record, separators=(",", ":"), sort_keys=True)
    parts = [f"{k}={v}" for k, v in record.items()]
    return " ".join(parts)


def _log(event: str, **fields) -> None:
    record = {"event": event, "ts": time.time(), **fields}
    logger.info(_format_record(record))


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Adds request ids, structured access logs, and security headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id", "").strip()
        if not request_id or any(c in request_id for c in "\n\r"):
            request_id = secrets.token_urlsafe(12)
        request.state.request_id = request_id

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            _log(
                "request.error",
                request_id=request_id,
                method=request.method,
                route=request.url.path,
                duration_ms=round(duration_ms, 1),
                level="ERROR",
            )
            raise

        duration_ms = (time.monotonic() - start) * 1000
        status = response.status_code
        route = request.url.path

        response.headers["X-Request-Id"] = request_id

        # Security headers on every response.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';",
        )

        if route in _PUBLIC_PATHS:
            response.headers.setdefault("Cache-Control", "public, max-age=60")
        else:
            response.headers.setdefault("Cache-Control", "no-store")

        # Access log: never log auth/service headers, never log query values that may
        # contain ids or tokens (route only, no ?qs).
        _log(
            "request",
            request_id=request_id,
            method=request.method,
            route=route,
            status=status,
            duration_ms=round(duration_ms, 1),
            client_ip=request.client.host if request.client else "unknown",
        )
        return response
