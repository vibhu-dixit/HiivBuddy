"""Cloudflare Turnstile verification for guest demo."""

from __future__ import annotations

import os
from typing import Any

import httpx

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def captcha_secret_configured() -> bool:
    return bool(os.environ.get("TURNSTILE_SECRET_KEY", "").strip())


def captcha_bypass_enabled() -> bool:
    return os.environ.get("GUEST_CAPTCHA_BYPASS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


async def verify_turnstile(token: str, remote_ip: str | None = None) -> bool:
    secret = os.environ.get("TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        return False

    payload: dict[str, str] = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(TURNSTILE_VERIFY_URL, data=payload)
        res.raise_for_status()
        data: dict[str, Any] = res.json()

    return bool(data.get("success"))


async def enforce_guest_captcha(captcha_token: str | None, remote_ip: str | None = None) -> None:
    from fastapi import HTTPException

    if captcha_bypass_enabled():
        return

    if not captcha_secret_configured():
        raise HTTPException(
            status_code=503,
            detail="Guest demo is temporarily unavailable. Please try again later.",
        )

    if not captcha_token or not captcha_token.strip():
        raise HTTPException(status_code=400, detail="Complete the captcha to start the demo.")

    ok = await verify_turnstile(captcha_token.strip(), remote_ip)
    if not ok:
        raise HTTPException(status_code=400, detail="Captcha verification failed. Please try again.")
