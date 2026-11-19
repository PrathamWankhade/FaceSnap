"""Tests for the best-effort webhook event bus."""

import pytest

from app.services import events


class InlineThread:
    """Run the worker synchronously so assertions are deterministic."""

    def __init__(self, target=None, daemon=True):
        self._target = target

    def start(self):
        if self._target is not None:
            self._target()


@pytest.fixture(autouse=True)
def inline_threads(monkeypatch):
    monkeypatch.setattr(events.threading, "Thread", InlineThread)
    monkeypatch.setattr(events.time, "sleep", lambda *_: None)


def test_emit_is_noop_without_destinations(monkeypatch):
    monkeypatch.setattr(events, "WEBHOOK_URLS", [])
    calls = []
    monkeypatch.setattr(events, "_deliver", lambda url, payload: calls.append((url, payload)) or True)

    assert events.emit("anything", {"a": 1}) is None
    assert calls == []


def test_allowlist_filters_events(monkeypatch):
    monkeypatch.setattr(events, "WEBHOOK_URLS", ["http://example.test/hook"])
    monkeypatch.setattr(events, "WEBHOOK_EVENTS", {"attendance.created"})

    calls = []
    monkeypatch.setattr(events, "_deliver", lambda url, payload: calls.append(payload["event"]) or True)

    events.emit("student.deleted", {"uid": "x"})
    assert calls == []

    events.emit("attendance.created", {"uid": "x"})
    assert calls == ["attendance.created"]


def test_emit_delivers_to_every_destination(monkeypatch):
    monkeypatch.setattr(events, "WEBHOOK_URLS", ["http://a.test/h", "http://b.test/h"])
    monkeypatch.setattr(events, "WEBHOOK_EVENTS", set())

    calls = []

    def fake_deliver(url, payload):
        calls.append((url, payload))
        return True

    monkeypatch.setattr(events, "_deliver", fake_deliver)

    events.emit("attendance.created", {"student_uid": "s1"})

    assert len(calls) == 2
    urls = {call[0] for call in calls}
    assert urls == {"http://a.test/h", "http://b.test/h"}
    for _url, payload in calls:
        assert payload["event"] == "attendance.created"
        assert payload["payload"] == {"student_uid": "s1"}
        assert "ts" in payload


def test_emit_retries_until_delivery_succeeds(monkeypatch):
    monkeypatch.setattr(events, "WEBHOOK_URLS", ["http://example.test/hook"])
    monkeypatch.setattr(events, "WEBHOOK_EVENTS", set())

    attempts = {"count": 0}

    def flaky_deliver(url, payload):
        attempts["count"] += 1
        return attempts["count"] >= 3

    monkeypatch.setattr(events, "_deliver", flaky_deliver)

    events.emit("x", {})

    assert attempts["count"] == 3
