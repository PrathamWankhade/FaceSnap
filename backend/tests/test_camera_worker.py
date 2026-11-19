"""Tests for camera worker health tracking and PTZ queue."""
from app.services.camera_worker import CameraWorkerManager, clear_ptz_queue, enqueue_ptz, ptz_queue


def test_health_transitions_and_reconnect_backoff():
    manager = CameraWorkerManager(base_backoff=1.0, max_backoff=8.0)

    health = manager.mark_failure(1, "connection refused")
    assert health.failures == 1
    assert health.reconnects == 1
    assert health.next_retry_at is not None
    assert manager.due_for_reconnect(1, now=health.next_retry_at + 0.1) is True
    assert manager.due_for_reconnect(1, now=health.next_retry_at - 0.1) is False

    # Repeated failures keep increasing backoff up to the cap.
    for _ in range(5):
        manager.mark_failure(1)
    final = manager.health(1)
    assert final.failures == 6
    assert final.next_retry_at is not None


def test_mark_online_resets_failures():
    manager = CameraWorkerManager()
    manager.mark_failure(1, "boom")
    manager.mark_online(1)
    health = manager.health(1)
    assert health.status == "online"
    assert health.failures == 0
    assert health.next_retry_at is None
    assert health.last_error is None


def test_ptz_queue_is_bounded_and_clearable():
    clear_ptz_queue(99)
    for i in range(105):
        enqueue_ptz(99, {"seq": i})
    queue = ptz_queue(99)
    assert len(queue) == 100
    assert queue[0]["seq"] == 5  # oldest 5 dropped
    clear_ptz_queue(99)
    assert ptz_queue(99) == []