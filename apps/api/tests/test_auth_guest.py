import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.rate_limit import reset_rate_limits_for_tests
from app.main import app


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_rate_limits_for_tests()
    yield
    reset_rate_limits_for_tests()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_guest_disabled_returns_403(monkeypatch):
    monkeypatch.setenv("GUEST_AUTH_ENABLED", "false")
    monkeypatch.setenv("GUEST_CAPTCHA_BYPASS", "true")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/auth/guest", json={})
    assert res.status_code == 403


@pytest.mark.anyio
async def test_guest_requires_captcha_without_bypass(monkeypatch):
    monkeypatch.setenv("GUEST_AUTH_ENABLED", "true")
    monkeypatch.delenv("GUEST_CAPTCHA_BYPASS", raising=False)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "test-secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/auth/guest", json={})
    assert res.status_code == 400
    assert "captcha" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_guest_unavailable_without_turnstile_secret(monkeypatch):
    monkeypatch.setenv("GUEST_AUTH_ENABLED", "true")
    monkeypatch.setenv("GUEST_CAPTCHA_BYPASS", "false")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(6):
            res = await client.post("/auth/guest", json={"captcha_token": "fake"})
        assert res.status_code == 503
        assert "temporarily unavailable" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_health_reports_guest_demo_readiness(monkeypatch):
    monkeypatch.setenv("GUEST_AUTH_ENABLED", "true")
    monkeypatch.delenv("GUEST_CAPTCHA_BYPASS", raising=False)
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["guest_demo"]["enabled"] is True
    assert body["guest_demo"]["captcha_configured"] is False
    assert body["guest_demo"]["ready"] is False


def test_guest_username_pattern():
    from app.auth.router import _GUEST_USERNAME_RE

    assert _GUEST_USERNAME_RE.fullmatch("guest_a1b2c3d4e5f6")
    assert not _GUEST_USERNAME_RE.fullmatch("guest_short")
