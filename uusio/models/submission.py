"""PRO submission records."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uusio.core.database import Base
from uusio.models.enums import SubmissionMethod, SubmissionStatus
from uusio.models.mixins import CustomerScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PROSubmission(UUIDPrimaryKeyMixin, CustomerScopedMixin, TimestampMixin, Base):
    __tablename__ = "pro_submissions"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    obligation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("epr_obligations.id", ondelete="CASCADE"), nullable=False, index=True)
    pro_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    submission_method: Mapped[SubmissionMethod] = mapped_column(String(20), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(String(20), nullable=False, default=SubmissionStatus.PENDING, index=True)
    report_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    obligation: Mapped["EPRObligation"] = relationship("EPRObligation", back_populates="submissions")  # type: ignore[name-defined]
    customer: Mapped["Customer"] = relationship("Customer")  # type: ignore[name-defined]
