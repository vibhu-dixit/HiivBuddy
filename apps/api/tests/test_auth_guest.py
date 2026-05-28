import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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


def test_guest_username_pattern():
    from app.auth.router import _GUEST_USERNAME_RE

    assert _GUEST_USERNAME_RE.fullmatch("guest_a1b2c3d4e5f6")
    assert not _GUEST_USERNAME_RE.fullmatch("guest_short")
