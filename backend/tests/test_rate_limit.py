from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import rate_limit
from app.core.rate_limit import InMemoryLoginRateLimiter


def _request(host: str):
    return SimpleNamespace(client=SimpleNamespace(host=host))


def test_login_rate_limit_applies_per_ip(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 2)
    monkeypatch.setattr(rate_limit.settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)
    limiter = InMemoryLoginRateLimiter()
    request = _request("127.0.0.1")

    limiter.register_failure(request, "one@example.com")
    limiter.register_failure(request, "two@example.com")

    with pytest.raises(HTTPException) as exc:
        limiter.check(request, "three@example.com")

    assert exc.value.status_code == 429


def test_login_rate_limit_applies_per_email(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 2)
    monkeypatch.setattr(rate_limit.settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)
    limiter = InMemoryLoginRateLimiter()

    limiter.register_failure(_request("127.0.0.1"), "user@example.com")
    limiter.register_failure(_request("127.0.0.2"), "user@example.com")

    with pytest.raises(HTTPException) as exc:
        limiter.check(_request("127.0.0.3"), "user@example.com")

    assert exc.value.status_code == 429
