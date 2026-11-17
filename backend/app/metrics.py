"""In-process counters for the Prometheus text endpoint.

Deliberately dependency-free: the exposition format is small and stable, and a
client library would add a background collector we do not need. Bounded label
sets only — never a raw path, student id or uid — so the metrics endpoint can be
scraped without leaking identifiers.

Thread safety: the app runs sync handlers in a thread pool, so every mutation
takes a lock. Contention is irrelevant at this scale.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Iterable

# Bucket upper bounds in seconds. Covers a fast health probe through a slow
# CPU-bound recognition call; anything above the last bucket counts as +Inf.
DEFAULT_BUCKETS: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Cosine-distance buckets for match drift monitoring (0 = identical, 1 = opposite).
MATCH_DISTANCE_BUCKETS: tuple[float, ...] = (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5, 0.75, 1.0)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Metrics:
    """Minimal Prometheus registry: request counters, latency histogram, auth/limit counters."""

    def __init__(self, buckets: Iterable[float] = DEFAULT_BUCKETS) -> None:
        self._buckets = tuple(sorted(buckets))
        self._match_buckets = MATCH_DISTANCE_BUCKETS
        self._lock = threading.Lock()
        # (method, route, status) -> count
        self._requests: dict[tuple[str, str, str], int] = defaultdict(int)
        # (method, route) -> {"sum", "count", "buckets": [count per bucket]}
        self._durations: dict[tuple[str, str], dict] = {}
        self._rate_limited = 0
        # status ("401"/"403") -> count
        self._auth_failures: dict[str, int] = defaultdict(int)
        self._started = time.monotonic()
        # route -> {"sum", "count", "buckets"} for match cosine distances (0..1)
        self._match_distances: dict[str, dict] = {}

    # -- recording ---------------------------------------------------------
    def record_request(
        self,
        method: str,
        route: str,
        status: int,
        duration_seconds: float,
    ) -> None:
        method = method.upper()
        route = route or "unmatched"
        status_text = str(status)
        with self._lock:
            self._requests[(method, route, status_text)] += 1
            if status == 401 or status == 403:
                self._auth_failures[status_text] += 1
            if status == 429:
                self._rate_limited += 1

            entry = self._durations.get((method, route))
            if entry is None:
                entry = {
                    "sum": 0.0,
                    "count": 0,
                    "buckets": [0] * len(self._buckets),
                }
                self._durations[(method, route)] = entry
            entry["sum"] += max(0.0, duration_seconds)
            entry["count"] += 1
            for index, bound in enumerate(self._buckets):
                if duration_seconds <= bound:
                    entry["buckets"][index] += 1

    def totals(self) -> tuple[int, int]:
        """Return (total_requests, server_error_requests) for alerting."""
        with self._lock:
            total = sum(self._requests.values())
            failures = sum(count for (m, r, s), count in self._requests.items() if s.startswith("5"))
        return total, failures

    def record_match_distance(self, distance: float, route: str = "detect") -> None:
        """Record a verified match's cosine distance for drift monitoring."""
        route = route or "unmatched"
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return
        if value < 0:
            value = 0.0
        if value > 1.0:
            value = 1.0
        buckets = self._match_buckets
        with self._lock:
            entry = self._match_distances.get(route)
            if entry is None:
                entry = {"sum": 0.0, "count": 0, "buckets": [0] * len(buckets)}
                self._match_distances[route] = entry
            entry["sum"] += value
            entry["count"] += 1
            for index, bound in enumerate(buckets):
                if value <= bound:
                    entry["buckets"][index] += 1

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._durations.clear()
            self._rate_limited = 0
            self._auth_failures.clear()
            self._started = time.monotonic()
            self._match_distances.clear()

    # -- exposition --------------------------------------------------------
    def render(self) -> str:
        with self._lock:
            requests = dict(self._requests)
            durations = {
                key: {
                    "sum": value["sum"],
                    "count": value["count"],
                    "buckets": list(value["buckets"]),
                }
                for key, value in self._durations.items()
            }
            rate_limited = self._rate_limited
            auth_failures = dict(self._auth_failures)
            uptime = time.monotonic() - self._started
            buckets = self._buckets
            match_buckets = self._match_buckets
            match_distances = {
                key: {"sum": v["sum"], "count": v["count"], "buckets": list(v["buckets"])}
                for key, v in self._match_distances.items()
            }
        lines: list[str] = [
            "# HELP facesnap_requests_total HTTP requests by method, route and status.",
            "# TYPE facesnap_requests_total counter",
        ]
        for (method, route, status), count in sorted(requests.items()):
            lines.append(
                "facesnap_requests_total"
                f'{{method="{_escape(method)}",route="{_escape(route)}",status="{_escape(status)}"}}'
                f" {count}"
            )

        lines += [
            "# HELP facesnap_request_duration_seconds HTTP request latency.",
            "# TYPE facesnap_request_duration_seconds histogram",
        ]
        for (method, route), entry in sorted(durations.items()):
            labels = f'method="{_escape(method)}",route="{_escape(route)}"'
            for bound, count in zip(buckets, entry["buckets"]):
                lines.append(
                    "facesnap_request_duration_seconds_bucket"
                    f'{{{labels},le="{bound}"}} {count}'
                )
            # +Inf must equal the total observation count (cumulative semantics).
            lines.append(
                f'facesnap_request_duration_seconds_bucket{{{labels},le="+Inf"}} {entry["count"]}'
            )
            lines.append(f"facesnap_request_duration_seconds_sum{{{labels}}} {entry['sum']:.6f}")
            lines.append(f"facesnap_request_duration_seconds_count{{{labels}}} {entry['count']}")

        lines += [
            "# HELP facesnap_rate_limited_total Requests rejected by the rate limiter.",
            "# TYPE facesnap_rate_limited_total counter",
            f"facesnap_rate_limited_total {rate_limited}",
            "# HELP facesnap_auth_failures_total 401/403 responses by status.",
            "# TYPE facesnap_auth_failures_total counter",
        ]
        for status, count in sorted(auth_failures.items()):
            lines.append(f'facesnap_auth_failures_total{{status="{_escape(status)}"}} {count}')

        lines += [
            "# HELP facesnap_match_distance Cosine distance of verified matches (drift monitoring).",
            "# TYPE facesnap_match_distance histogram",
        ]
        for route, entry in sorted(match_distances.items()):
            labels = f'route="{_escape(route)}"'
            for bound, count in zip(match_buckets, entry["buckets"]):
                lines.append(
                    "facesnap_match_distance_bucket"
                    f'{{{labels},le="{bound}"}} {count}'
                )
            lines.append(
                f'facesnap_match_distance_bucket{{{labels},le="+Inf"}} {entry["count"]}'
            )
            lines.append(f"facesnap_match_distance_sum{{{labels}}} {entry['sum']:.6f}")
            lines.append(f"facesnap_match_distance_count{{{labels}}} {entry['count']}")

        lines += [
            "# HELP facesnap_process_uptime_seconds Seconds since this process started.",
            "# TYPE facesnap_process_uptime_seconds gauge",
            f"facesnap_process_uptime_seconds {uptime:.3f}",
        ]
        return "\n".join(lines) + "\n"


metrics = Metrics()
