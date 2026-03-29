from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DebateRun(Base):
    __tablename__ = "debate_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    context: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(128))
    transcript: Mapped[str] = mapped_column(Text, default="")
    final_report_json: Mapped[str] = mapped_column(Text, default="{}")
