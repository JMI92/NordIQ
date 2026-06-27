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


class PROInvoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Incoming invoice received from a PRO organisation.

    These are the costs we (or our customer) pay to PROs. Recording them
    allows margin reconciliation: customer invoice - PRO invoice = actual margin.

    invoice_type mirrors Invoice.invoice_type:
      - monthly       material fee invoices from PRO
      - annual        yearly membership / compliance fee from PRO
      - registration  one-time registration fee from PRO
    """

    __tablename__ = "pro_invoices"

    pro_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pro_organisations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The outgoing customer invoice this PRO invoice corresponds to (optional)
    customer_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pro_invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly", index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # received / paid / disputed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", index=True)
    received_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw line items from PRO invoice for reference
    line_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<PROInvoice {self.pro_invoice_number} [{self.invoice_type}/{self.status}] {self.amount} {self.currency}>"
