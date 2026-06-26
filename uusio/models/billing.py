"""Billing / invoice model."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uusio.core.database import Base
from uusio.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Customer invoice.

    invoice_type:
      - monthly       material reporting fees + service fee
      - annual        yearly PRO membership fees (auto-generated each January)
      - registration  one-time PRO registration fees
      - manual        admin-created ad hoc invoice
    """

    __tablename__ = "invoices"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    # monthly / annual / registration / manual
    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    service_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("30.00"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    # draft / sent / paid / overdue / cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    # Reporting period this invoice covers (monthly/annual)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"description": str, "quantity": float, "unit_price": float, "margin_pct": float|null, "total": float}]
    line_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Placeholder for accounting software export (Procountor etc.)
    accounting_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    accounting_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} [{self.invoice_type}/{self.status}] {self.amount} {self.currency}>"
