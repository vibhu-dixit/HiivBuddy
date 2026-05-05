from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))

    debate_runs: Mapped[list["DebateRun"]] = relationship(back_populates="user")


class DebateRun(Base):
    __tablename__ = "debate_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    context: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(128))
    transcript: Mapped[str] = mapped_column(Text, default="")
    final_report_json: Mapped[str] = mapped_column(Text, default="{}")

    user: Mapped["User | None"] = relationship(back_populates="debate_runs")
