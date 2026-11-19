"""Email (SMTP) alert channel tests for app.services.notifier."""
import sys
import types

from app.services import notifier


def test_notifier_email_requires_recipient_and_host(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_EMAIL_TO", "")
    monkeypatch.setattr(notifier, "SMTP_HOST", "")
    assert notifier._send_email("s", "b") is False


def test_notifier_email_sends_via_smtp(monkeypatch):
    sent = []

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent.append(msg)

    monkeypatch.setitem(sys.modules, "smtplib", types.SimpleNamespace(SMTP=_FakeSMTP))
    monkeypatch.setattr(notifier, "ALERT_EMAIL_TO", "ops@example.edu")
    monkeypatch.setattr(notifier, "SMTP_HOST", "smtp.example.edu")
    monkeypatch.setattr(notifier, "SMTP_USER", "")
    monkeypatch.setattr(notifier, "SMTP_PASSWORD", "")

    assert notifier._send_email("FaceSnap alert: test", "body") is True
    assert len(sent) == 1
    assert sent[0]["Subject"] == "FaceSnap alert: test"
    assert sent[0]["To"] == "ops@example.edu"


def test_notifier_email_fires_when_only_email_configured(monkeypatch):
    # Run the delivery worker synchronously so the assertion sees it.
    class _ImmediateThread:
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(notifier.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(notifier, "ALERT_WEBHOOK_URL", "")
    monkeypatch.setattr(notifier, "ALERT_EMAIL_TO", "ops@example.edu")
    monkeypatch.setattr(notifier, "SMTP_HOST", "smtp.example.edu")
    monkeypatch.setattr(notifier, "ALERT_COOLDOWN_SECONDS", 0)
    notifier.reset_cooldowns()
    calls = []
    monkeypatch.setattr(
        notifier, "_send_email", lambda subject, body: calls.append(subject) or True
    )

    assert notifier.notify("drift_alert", {"score": 0.9}) is True
    assert calls and calls[0] == "FaceSnap alert: drift_alert"


def test_notifier_notify_disabled_when_no_channel(monkeypatch):
    monkeypatch.setattr(notifier, "ALERT_WEBHOOK_URL", "")
    monkeypatch.setattr(notifier, "ALERT_EMAIL_TO", "")
    notifier.reset_cooldowns()
    assert notifier.notify("x", {}) is False
