"""Best-effort webhook event bus.

Generalizes the alerting notifier into a general-purpose event delivery
mechanism. Events are delivered asynchronously with retry. Disabled by default
(``WEBHOOK_URLS`` empty).

Config:
  WEBHOOK_URLS     comma-separated destination URLs
  WEBHOOK_EVENTS   comma-separated allowlist (empty = all events)
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

WEBHOOK_URLS = [u.strip() for u in os.getenv("WEBHOOK_URLS", "").split(",") if u.strip()]
WEBHOOK_EVENTS = {e.strip() for e in os.getenv("WEBHOOK_EVENTS", "").split(",") if e.strip()}


def _deliver(url: str, payload: dict[str, Any]) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def emit(event: str, payload: dict[str, Any] | None = None) -> None:
    """Emit an event to all configured webhook URLs (allowlist-filtered)."""
    if WEBHOOK_URLS and WEBHOOK_EVENTS and event not in WEBHOOK_EVENTS:
        return
    if not WEBHOOK_URLS:
        return
    body = {"event": event, "ts": time.time(), "payload": payload or {}}

    def _worker() -> None:
        for url in WEBHOOK_URLS:
            for attempt in range(3):
                if _deliver(url, body):
                    break
                time.sleep(0.5 * (2 ** attempt))

    threading.Thread(target=_worker, daemon=True).start()