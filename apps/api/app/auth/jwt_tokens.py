import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

# Symmetric signing (HMAC). HS384 = HMAC-SHA-384; override via JWT_ALGORITHM if needed.
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS384")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

# Require a strong secret in production; insecure default for local dev only.
_env_secret = os.environ.get("JWT_SECRET", "").strip()
JWT_SECRET = _env_secret or "hiivbuddy-dev-insecure-jwt-secret"


def create_access_token(*, user_id: int, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def decode_token_sub(token: str) -> int | None:
    try:
        data = decode_token(token)
        sub = data.get("sub")
        if sub is None:
            return None
        return int(sub)
    except JWTError:
        return None
