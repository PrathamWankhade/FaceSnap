"""Best-effort alerting for FaceSnap.

A single optional webhook URL receives JSON payloads when the health endpoint
degrades or the request error rate exceeds a configured threshold. Alerting is
deliberately dependency-free (urllib) and fail-safe: a broken webhook never
breaks a request, and a disabled webhook (the default) is a no-op.

Configuration (see app/config.py):
  ALERT_WEBHOOK_URL            empty disables alerting
  ALERT_ERROR_RATE_THRESHOLD   fraction of 5xx responses that triggers an alert
  ALERT_COOLDOWN_SECONDS       per-event cooldown to avoid alert storms
  ALERT_MIN_REQUESTS           minimum sample size before an error-rate alert
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from app.config import (
    ALERT_COOLDOWN_SECONDS,
    ALERT_ERROR_RATE_THRESHOLD,
    ALERT_MIN_REQUESTS,
    ALERT_WEBHOOK_URL,
)

_lock = threading.Lock()
_last_fired: dict[str, float] = {}


def _deliver(url: str, payload: dict[str, Any]) -> bool:
    """POST a JSON payload to the webhook. Returns True on 2xx."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _cooldown_ok(event: str) -> bool:
    now = time.monotonic()
    with _lock:
        last = _last_fired.get(event)
        if last is not None and now - last < ALERT_COOLDOWN_SECONDS:
            return False
        _last_fired[event] = now
        return True


def notify(event: str, payload: dict[str, Any] | None = None) -> bool:
    """Fire an alert for ``event`` if configured and not in cooldown.

    Returns True when a delivery was attempted (and succeeded). Never raises.
    """
    url = ALERT_WEBHOOK_URL
    if not url:
        return False
    if not _cooldown_ok(event):
        return False

    body = {"event": event, "ts": time.time(), "payload": payload or {}}

    def _worker() -> None:
        try:
            _deliver(url, body)
        except Exception:  # pragma: no cover - _deliver already guards
            pass

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return True


def reset_cooldowns() -> None:
    """Test helper: clear the in-memory cooldown map."""
    with _lock:
        _last_fired.clear()


def health_degraded(components: dict[str, Any]) -> bool:
    """Notify when a hard dependency is down. Returns whether an alert fired."""
    hard = ("database", "vector_db", "face_model")
    if any(not components.get(name, False) for name in hard):
        return notify("health_degraded", {"components": components})
    return False


def error_rate_spike(total: int, failures: int) -> bool:
    """Notify when the 5xx/4xx-auth failure ratio exceeds the threshold."""
    if total < ALERT_MIN_REQUESTS:
        return False
    rate = failures / total if total else 0.0
    if rate >= ALERT_ERROR_RATE_THRESHOLD:
        return notify("error_rate_spike", {"total": total, "failures": failures, "rate": rate})
    return False


def drift_spike(route: str, rolling_mean: float, threshold: float) -> bool:
    """Notify when the rolling mean of match distances exceeds the threshold."""
    if rolling_mean >= threshold:
        return notify("drift_spike", {"route": route, "rolling_mean": rolling_mean, "threshold": threshold})
    return False