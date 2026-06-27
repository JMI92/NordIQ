"""PRO pricing and margin configuration."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uusio.core.database import Base
from uusio.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PRoPricing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pricing for a specific PRO, waste stream and fee type.

    fee_type:
      - registration  one-time fee when producer registers, passed through at cost
      - annual        yearly membership fee, passed through at cost
      - material      per-kg reporting fee, margin applied on top
    """

    __tablename__ = "pro_pricing"
    __table_args__ = (
        UniqueConstraint("pro_id", "waste_stream", "fee_type", "effective_date", name="uq_pro_pricing"),
    )

    pro_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pro_organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # packaging / weee / batteries / ev_batteries / tyres / textiles
    waste_stream: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # registration / annual / material
    fee_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # For material fees: price per kg. For registration/annual: flat fee.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    pro: Mapped["PROOrganisation"] = relationship("PROOrganisation")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<PRoPricing pro={self.pro_id} {self.waste_stream}/{self.fee_type} {self.amount} {self.currency}>"


class MarginSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Margin percentage applied to material fees only.

    If pro_id is NULL, this is the global default.
    PRO-specific settings override the global default.
    """

    __tablename__ = "margin_settings"

    # NULL = global default
    pro_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pro_organisations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    margin_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("15.00"))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        scope = f"pro={self.pro_id}" if self.pro_id else "global"
        return f"<MarginSettings {scope} {self.margin_percentage}%>"
