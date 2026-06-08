"""PRO submission records."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nordiq.core.database import Base
from nordiq.models.enums import SubmissionMethod, SubmissionStatus
from nordiq.models.mixins import CustomerScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PROSubmission(UUIDPrimaryKeyMixin, CustomerScopedMixin, TimestampMixin, Base):
    """A single submission attempt to a Producer Responsibility Organisation.

    Submission is idempotent — retrying a failed submission creates a new
    PROSubmission row rather than mutating the existing one, preserving the
    full attempt history for audit purposes.
    """

    __tablename__ = "pro_submissions"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("epr_obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pro_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    submission_method: Mapped[SubmissionMethod] = mapped_column(String(20), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        String(20), nullable=False, default=SubmissionStatus.PENDING, index=True
    )
    # Path or URL to the generated report file
    report_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw response body from the PRO's API/portal
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # relationships
    obligation: Mapped["EPRObligation"] = relationship("EPRObligation", back_populates="submissions")  # type: ignore[name-defined]
    customer: Mapped["Customer"] = relationship("Customer")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<PROSubmission {self.pro_id} [{self.status}] attempt #{self.retry_count}>"
