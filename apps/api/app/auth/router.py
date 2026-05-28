import os
import re
import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_tokens import create_access_token
from app.auth.password import hash_password, verify_password
from app.auth.captcha import enforce_guest_captcha
from app.auth.schemas import GuestRequest, LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.db.models import User
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
_GUEST_USERNAME_RE = re.compile(r"^guest_[a-f0-9]{12}$")


def is_guest_user(user: User) -> bool:
    return bool(_GUEST_USERNAME_RE.fullmatch(user.username))


def _guest_auth_enabled() -> bool:
    return os.environ.get("GUEST_AUTH_ENABLED", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    stripped = body.username.strip()
    if not _USERNAME_RE.fullmatch(stripped):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3–32 characters: letters, digits, underscore only",
        )
    username_store = stripped.lower()

    pw_hash = hash_password(body.password)
    user = User(username=username_store, password_hash=pw_hash)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")
    await session.refresh(user)

    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(
        access_token=token,
        user=UserPublic(id=user.id, username=user.username),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    u = body.username.strip().lower()
    result = await session.execute(select(User).where(User.username == u))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(
        access_token=token,
        user=UserPublic(id=user.id, username=user.username),
    )


@router.post("/guest", response_model=TokenResponse)
async def guest_session(
    body: GuestRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    if not _guest_auth_enabled():
        raise HTTPException(status_code=403, detail="Guest access is disabled")

    client_ip = request.client.host if request.client else None
    await enforce_guest_captcha(body.captcha_token, client_ip)

    guest_id = uuid.uuid4().hex[:12]
    username = f"guest_{guest_id}"
    if not _GUEST_USERNAME_RE.fullmatch(username):
        raise HTTPException(status_code=500, detail="Failed to create guest session")

    pw = secrets.token_urlsafe(32)
    user = User(username=username, password_hash=hash_password(pw))
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user_id=user.id, username=user.username, guest=True)
    return TokenResponse(
        access_token=token,
        user=UserPublic(id=user.id, username=user.username),
    )
