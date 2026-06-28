"""Persistent chat history for the portal compliance assistant."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from uusio.core.database import Base
from uusio.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ChatHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One message in a customer's ongoing conversation with the compliance assistant.

    role: "user" | "assistant"
    Messages are loaded in created_at order to reconstruct conversation context.
    """

    __tablename__ = "chat_history"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<ChatHistory customer={self.customer_id} role={self.role}>"
