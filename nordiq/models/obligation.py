"""EPR obligation, EPR rate table, and reporting deadline models."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nordiq.core.database import Base
from nordiq.models.enums import MaterialType, ObligationStatus, ProductCategory
from nordiq.models.mixins import CustomerScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EPRObligation(UUIDPrimaryKeyMixin, CustomerScopedMixin, TimestampMixin, Base):
    """A calculated EPR obligation for one customer, country, period, and product category.

    Once status transitions to FINALISED the record is immutable — no further edits.
    calculation_snapshot stores the exact inputs and rate schedule used so reports
    can be reproduced years later even after rates change.

    All monetary amounts use Numeric(18, 4) — never float.
    """

    __tablename__ = "epr_obligations"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    pro_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_category: Mapped[ProductCategory] = mapped_column(String(50), nullable=False, index=True)
    reporting_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_period_end: Mapped[date] = mapped_column(Date, nullable=False)

    total_weight_kg: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    fee_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    status: Mapped[ObligationStatus] = mapped_column(
        String(20), nullable=False, default=ObligationStatus.DRAFT, index=True
    )
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Immutable snapshot of all inputs + rates used — required for auditability
    calculation_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="obligations")  # type: ignore[name-defined]
    submissions: Mapped[list["PROSubmission"]] = relationship(  # type: ignore[name-defined]
        "PROSubmission", back_populates="obligation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EPRObligation {self.country_code} {self.product_category} {self.reporting_period_start}/{self.reporting_period_end} [{self.status}]>"


class EPRRate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """EPR fee rate per kg for a given country, product category, and material type.

    Rates are stored in the database (not hardcoded) so they can be updated
    when regulations change without deploying new code. A regulation_reference
    column links each rate to its legal source document.

    valid_to=NULL means the rate is currently in effect.
    """

    __tablename__ = "epr_rates"
    __table_args__ = (
        UniqueConstraint(
            "country_code", "product_category", "material_type", "valid_from",
            name="uq_epr_rate_country_category_material_from",
        ),
    )

    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    product_category: Mapped[ProductCategory] = mapped_column(String(50), nullable=False, index=True)
    material_type: Mapped[MaterialType] = mapped_column(String(50), nullable=False, index=True)
    rate_per_kg: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    regulation_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # EPR structural extensions (PPWR / eco-modulation / SUP)
    fixed_annual_fee_eur = mapped_column(Numeric(18, 4), nullable=True)
    eco_modulation_factor = mapped_column(Numeric(8, 4), nullable=False, server_default="1.0000")
    packaging_stream = mapped_column(String(20), nullable=True)
    is_sup_surcharge = mapped_column(Boolean, nullable=False, server_default="false")
    ppwr_effective_from = mapped_column(Date, nullable=True)

    def __repr__(self) -> str:
        return f"<EPRRate {self.country_code} {self.material_type} {self.rate_per_kg}/kg from {self.valid_from}>"


class ReportingDeadline(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Statutory reporting deadline for a country and product category.

    Used by the scheduler to trigger warnings at 30/14/7/1 day intervals
    and to auto-calculate and auto-submit when the customer has opted in.
    """

    __tablename__ = "reporting_deadlines"
    __table_args__ = (
        UniqueConstraint(
            "country_code", "product_category", "reporting_period_end",
            name="uq_deadline_country_category_period",
        ),
    )

    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    product_category: Mapped[ProductCategory] = mapped_column(String(50), nullable=False, index=True)
    reporting_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    submission_deadline: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pro_id: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:
        return f"<ReportingDeadline {self.country_code} {self.product_category} due {self.submission_deadline}>"
