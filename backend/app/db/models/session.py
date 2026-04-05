from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String, default="Untitled Analysis")
    idea: Mapped[str] = mapped_column(String, nullable=False)
    graph_state: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"nodes": [], "edges": []}
    )
    selected_model: Mapped[str] = mapped_column(
        String, default="claude-sonnet-4-6"
    )
    context_summary: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
    context_summary_covers_up_to: Mapped[int | None] = mapped_column(
        nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="sessions")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.message_index",
    )
