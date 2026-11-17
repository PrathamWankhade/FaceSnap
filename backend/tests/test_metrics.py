"""Metrics exposition: bounded labels, cumulative histogram semantics, no identifiers."""
from fastapi.testclient import TestClient

from app.main import app
from app.metrics import Metrics


def test_request_counter_and_histogram_render():
    registry = Metrics(buckets=(0.1, 1.0))
    registry.record_request("post", "/api/attendance", 200, 0.05)
    registry.record_request("POST", "/api/attendance", 200, 0.5)
    registry.record_request("GET", "/api/health/live", 200, 0.001)
    registry.record_request("GET", "/api/students/{student_id}", 403, 0.002)

    text = registry.render()

    assert (
        'facesnap_requests_total{method="POST",route="/api/attendance",status="200"} 2'
        in text
    )
    # Cumulative histogram buckets: both observations are <= 1.0s, one <= 0.1s.
    assert (
        'facesnap_request_duration_seconds_bucket{method="POST",route="/api/attendance",le="0.1"} 1'
        in text
    )
    assert (
        'facesnap_request_duration_seconds_bucket{method="POST",route="/api/attendance",le="1.0"} 2'
        in text
    )
    assert (
        'facesnap_request_duration_seconds_bucket{method="POST",route="/api/attendance",le="+Inf"} 2'
        in text
    )
    assert 'facesnap_request_duration_seconds_count{method="POST",route="/api/attendance"} 2' in text
    assert 'facesnap_auth_failures_total{status="403"} 1' in text
    assert "facesnap_process_uptime_seconds" in text
    # Route templates only; no raw path or identifier can appear as a label.
    assert "student_id=" not in text


def test_rate_limited_counter_tracks_429_only():
    registry = Metrics()
    registry.record_request("POST", "/api/verify_liveness", 429, 0.01)
    registry.record_request("POST", "/api/verify_liveness", 200, 0.01)
    text = registry.render()
    assert "facesnap_rate_limited_total 1" in text


def test_label_values_are_escaped():
    registry = Metrics()
    registry.record_request("GET", '/api/odd"route', 200, 0.01)
    assert '\\"route' in registry.render()


def test_metrics_endpoint_serves_prometheus_text():
    client = TestClient(app)
    res = client.get("/api/metrics")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert "facesnap_requests_total" in res.text
    assert "facesnap_process_uptime_seconds" in res.text
