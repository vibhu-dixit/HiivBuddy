import os

import pytest
from fastapi import HTTPException

from app.auth.rate_limit import enforce_ip_rate_limit, reset_rate_limits_for_tests


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_rate_limits_for_tests()
    yield
    reset_rate_limits_for_tests()


def test_ip_rate_limit_blocks_after_max():
    os.environ["GUEST_AUTH_IP_RATE_LIMIT"] = "2"
    for _ in range(2):
        enforce_ip_rate_limit(ip="203.0.113.10", bucket="guest_auth", max_requests=2, window_sec=3600)
    with pytest.raises(HTTPException) as exc:
        enforce_ip_rate_limit(ip="203.0.113.10", bucket="guest_auth", max_requests=2, window_sec=3600)
    assert exc.value.status_code == 429


def test_ip_rate_limit_isolated_by_ip():
    enforce_ip_rate_limit(ip="203.0.113.10", bucket="guest_auth", max_requests=1, window_sec=3600)
    with pytest.raises(HTTPException):
        enforce_ip_rate_limit(ip="203.0.113.10", bucket="guest_auth", max_requests=1, window_sec=3600)
    # Different IP should still be allowed
    enforce_ip_rate_limit(ip="203.0.113.11", bucket="guest_auth", max_requests=1, window_sec=3600)


def test_client_ip_prefers_x_forwarded_for():
    from starlette.requests import Request

    from app.auth.rate_limit import client_ip

    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.1, 10.0.0.1")],
        "client": ("127.0.0.1", 12345),
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
    }
    req = Request(scope)
    assert client_ip(req) == "203.0.113.1"
