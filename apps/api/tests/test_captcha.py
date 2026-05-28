import pytest

from app.auth.captcha import captcha_bypass_enabled, captcha_secret_configured, verify_turnstile


def test_captcha_bypass_env(monkeypatch):
    monkeypatch.delenv("GUEST_CAPTCHA_BYPASS", raising=False)
    assert captcha_bypass_enabled() is False
    monkeypatch.setenv("GUEST_CAPTCHA_BYPASS", "true")
    assert captcha_bypass_enabled() is True


def test_captcha_secret_configured(monkeypatch):
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    assert captcha_secret_configured() is False
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "secret")
    assert captcha_secret_configured() is True


@pytest.mark.anyio
async def test_verify_turnstile_no_secret(monkeypatch):
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    assert await verify_turnstile("token") is False
