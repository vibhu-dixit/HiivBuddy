"""Additive migrations after create_all (legacy DBs missing columns)."""

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection


async def migrate_schema(conn: AsyncConnection) -> None:
    def _migrate(connection) -> None:
        inspector = inspect(connection)
        if "debate_runs" not in inspector.get_table_names():
            return
        cols = {c["name"] for c in inspector.get_columns("debate_runs")}
        if "user_id" not in cols:
            connection.execute(
                text("ALTER TABLE debate_runs ADD COLUMN user_id INTEGER REFERENCES users(id)"),
            )
            # Do not DELETE legacy rows: pre-migration runs would all have user_id NULL.
            # They remain nullable until backfilled; list endpoints filter by user_id.

    await conn.run_sync(_migrate)
