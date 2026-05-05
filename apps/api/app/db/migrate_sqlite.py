"""SQLite-only additive migrations (create_all does not alter existing tables)."""

from sqlalchemy.ext.asyncio import AsyncConnection


async def migrate_sqlite_schema(conn: AsyncConnection) -> None:
    """Add columns / tables missing from older installs."""

    def _migrate(connection) -> None:
        try:
            rows = connection.exec_driver_sql("PRAGMA table_info(debate_runs)").fetchall()
        except Exception:
            return
        col_names = {r[1] for r in rows}
        if not col_names:
            return
        if "user_id" not in col_names:
            connection.exec_driver_sql("ALTER TABLE debate_runs ADD COLUMN user_id INTEGER")
        connection.exec_driver_sql("DELETE FROM debate_runs WHERE user_id IS NULL")

    await conn.run_sync(_migrate)
