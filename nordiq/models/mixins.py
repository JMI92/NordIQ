"""SQLAlchemy mixins shared across models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """Primary key as UUID, auto-generated."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )


class TimestampMixin:
    """created_at and updated_at columns, auto-managed."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CustomerScopedMixin:
    """Adds customer_id foreign key — ALL tenant-scoped tables must use this.

    IMPORTANT: Every query on a customer-scoped table MUST filter by customer_id.
    The application layer enforces this; this mixin makes the column mandatory.
    """

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
