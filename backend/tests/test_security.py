"""Security regression tests: production guards, role gating, rate limiting."""
import asyncio

import pytest
from fastapi import HTTPException

import app.auth as auth_module
from app.auth import require_camera_caller, require_roles
from app.db import User
from app.main import _validate_runtime
from app.rate_limit import SlidingWindowLimiter


def _user(role: str) -> User:
    return User(id="test-user", email="test@example.com", role=role)


def test_production_refuses_the_auth_bypass():
    with pytest.raises(RuntimeError, match="REQUIRE_AUTH"):
        _validate_runtime("production", False, ["https://app.example.com"])


def test_production_refuses_wildcard_cors():
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _validate_runtime("production", True, ["*"])
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _validate_runtime("production", True, [])


def test_production_with_safe_config_starts():
    _validate_runtime("production", True, ["https://app.example.com"])


def test_development_warns_loudly_about_the_bypass(capsys):
    _validate_runtime("development", False, ["*"])
    output = capsys.readouterr().out
    assert "DEVELOPMENT AUTH BYPASS ENABLED" in output


def test_students_cannot_use_staff_only_routes():
    checker = require_roles("admin", "operator")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(checker(user=_user("student")))
    assert exc.value.status_code == 403


def test_operators_can_use_staff_only_routes():
    checker = require_roles("admin", "operator")
    assert asyncio.run(checker(user=_user("operator"))).role == "operator"


def test_valid_service_key_grants_camera_access(monkeypatch):
    monkeypatch.setattr(auth_module, "PI_SERVICE_KEY", "test-service-key")
    result = asyncio.run(
        require_camera_caller(
            authorization=None,
            x_service_key="test-service-key",
            db=None,
        )
    )
    assert result["uid"] == "pi-service"


def test_sliding_window_limiter_blocks_after_limit():
    limiter = SlidingWindowLimiter(2, window_seconds=60)
    assert limiter.allow("client") is True
    assert limiter.allow("client") is True
    assert limiter.allow("client") is False
    # Other clients are unaffected.
    assert limiter.allow("other") is True


def test_rate_limit_can_be_disabled():
    assert SlidingWindowLimiter(0).allow("anything") is True
