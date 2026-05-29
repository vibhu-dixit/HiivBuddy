"""In-memory per-IP rate limiting for guest demo endpoints."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request

_lock = Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def client_ip(request: Request) -> str:
    """Prefer X-Forwarded-For (Render/proxy) then direct client host."""
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_ip_rate_limit(
    *,
    ip: str,
    bucket: str,
    max_requests: int,
    window_sec: int,
) -> None:
    key = f"{bucket}:{ip}"
    now = time.monotonic()
    cutoff = now - window_sec
    with _lock:
        recent = [t for t in _hits[key] if t > cutoff]
        if len(recent) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests from this network. Please try again later.",
            )
        recent.append(now)
        _hits[key] = recent


def enforce_guest_auth_rate_limit(request: Request) -> None:
    enforce_ip_rate_limit(
        ip=client_ip(request),
        bucket="guest_auth",
        max_requests=_env_int("GUEST_AUTH_IP_RATE_LIMIT", 5),
        window_sec=_env_int("GUEST_AUTH_IP_RATE_WINDOW_SEC", 3600),
    )


def enforce_guest_debate_rate_limit(request: Request) -> None:
    enforce_ip_rate_limit(
        ip=client_ip(request),
        bucket="guest_debate",
        max_requests=_env_int("GUEST_DEBATE_IP_RATE_LIMIT", 3),
        window_sec=_env_int("GUEST_DEBATE_IP_RATE_WINDOW_SEC", 3600),
    )


def reset_rate_limits_for_tests() -> None:
    """Test helper only."""
    with _lock:
        _hits.clear()
