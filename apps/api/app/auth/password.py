"""Password hashing using bcrypt on SHA-256 of UTF-8 password (works with bcrypt's 72-byte secret limit)."""

import bcrypt
import hashlib


def _digest(plain: str) -> bytes:
    return hashlib.sha256(plain.encode("utf-8")).digest()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_digest(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_digest(plain), password_hash.encode("ascii"))
    except ValueError:
        return False
