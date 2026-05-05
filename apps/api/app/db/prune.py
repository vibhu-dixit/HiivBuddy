"""Trim stored debate runs so the DB does not grow without bound (per-user cap)."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DebateRun

# Align with `MAX_ITEMS` in apps/web decision-room debateHistory.
MAX_STORED_RUNS = 60


async def prune_excess_runs_for_user(
    session: AsyncSession,
    user_id: int,
    *,
    keep: int = MAX_STORED_RUNS,
) -> int:
    """Delete oldest rows for this user until at most `keep` remain. Returns rows deleted."""
    count_r = await session.execute(
        select(func.count()).select_from(DebateRun).where(DebateRun.user_id == user_id),
    )
    total = int(count_r.scalar_one() or 0)
    excess = total - keep
    if excess <= 0:
        return 0
    ids_r = await session.execute(
        select(DebateRun.id)
        .where(DebateRun.user_id == user_id)
        .order_by(DebateRun.id.asc())
        .limit(excess),
    )
    ids = [row[0] for row in ids_r.all()]
    if not ids:
        return 0
    await session.execute(delete(DebateRun).where(DebateRun.id.in_(ids)))
    await session.commit()
    return len(ids)


async def prune_all_users_excess_runs(session: AsyncSession, *, keep: int = MAX_STORED_RUNS) -> int:
    """Run per-user pruning for every user who has debate rows. Returns total rows deleted."""
    uid_r = await session.execute(select(DebateRun.user_id).distinct().where(DebateRun.user_id.is_not(None)))
    user_ids = [row[0] for row in uid_r.all() if row[0] is not None]
    deleted = 0
    for uid in user_ids:
        deleted += await prune_excess_runs_for_user(session, uid, keep=keep)
    return deleted
