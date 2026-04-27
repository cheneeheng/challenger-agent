from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(String, nullable=False)
    message_index: Mapped[int] = mapped_column(nullable=False)
    # metadata_ avoids collision with SQLAlchemy's reserved .metadata attribute
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    session: Mapped["Session"] = relationship(back_populates="messages")  # noqa: F821
