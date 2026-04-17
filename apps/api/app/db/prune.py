"""Trim stored debate runs so the DB does not grow without bound."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DebateRun

# Align with `MAX_ITEMS` in apps/web decision-room debateHistory.
MAX_STORED_RUNS = 60


async def prune_excess_runs(session: AsyncSession, *, keep: int = MAX_STORED_RUNS) -> int:
    """Delete oldest rows until at most `keep` remain. Returns number of rows deleted."""
    count_r = await session.execute(select(func.count()).select_from(DebateRun))
    total = int(count_r.scalar_one() or 0)
    excess = total - keep
    if excess <= 0:
        return 0
    ids_r = await session.execute(
        select(DebateRun.id).order_by(DebateRun.id.asc()).limit(excess),
    )
    ids = [row[0] for row in ids_r.all()]
    if not ids:
        return 0
    await session.execute(delete(DebateRun).where(DebateRun.id.in_(ids)))
    await session.commit()
    return len(ids)
