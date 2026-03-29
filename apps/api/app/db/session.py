import os
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "hiivbuddy.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    from app.db import models as _models  # noqa: F401 — register tables on Base.metadata

    os.makedirs(DATA_DIR, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
