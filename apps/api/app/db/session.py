import os
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Ensure DATABASE_URL is visible when defined only in .env files (Session uses os.environ, not pydantic).
_api_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_api_root / ".env")
load_dotenv(_api_root.parent / ".env")


def _normalize_database_url(raw: str) -> str:
    # Strip BOM / whitespace; drop accidental wrapping quotes from .env edits on Windows.
    raw = raw.strip().lstrip("\ufeff").strip().strip('"').strip("'")
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


def _require_valid_database_url(url: str) -> None:
    try:
        make_url(url)
    except Exception as e:
        raise RuntimeError(
            "DATABASE_URL is set but is not a valid PostgreSQL URL. "
            "Use one line, no spaces around '=', e.g. "
            "postgresql://hiivbuddy:hiivbuddy@localhost:5435/hiivbuddy — "
            "if the password has @ : / ? # special characters, URL-encode them. "
            f"Underlying error: {e}",
        ) from e


_raw_db_url = _normalize_database_url(os.environ.get("DATABASE_URL", ""))
if not _raw_db_url:
    raise RuntimeError(
        "DATABASE_URL is required (PostgreSQL). Example: "
        "postgresql://user:pass@localhost:5435/hiivbuddy. "
        "On Render, link a Postgres instance to inject DATABASE_URL.",
    )
_require_valid_database_url(_raw_db_url)
DATABASE_URL = _raw_db_url


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0
    }
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    from app.db import models as _models  # noqa: F401 — register tables on Base.metadata
    from app.db.migrate_schema import migrate_schema

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await migrate_schema(conn)
