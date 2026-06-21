"""Product material composition (master data) and monthly sales volume models."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uusio.core.database import Base
from uusio.models.enums import MaterialType
from uusio.models.mixins import CustomerScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ProductMaterialComposition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """How much of each material a product contains per unit sold.

    This is the stable master data that defines the 'recipe' of a product.
    Calculation engine multiplies this by MonthlySalesVolume.units_sold to
    get total material weight for the reporting period.
    """

    __tablename__ = "product_material_compositions"
    __table_args__ = (
        UniqueConstraint("product_id", "material_type", "is_packaging", name="uq_pmc_product_material_packaging"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # True = this is packaging material, False = it's the product body itself
    is_packaging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Weight in kg per single unit sold
    weight_per_unit_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    # household / commercial / None
    packaging_stream: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="compositions")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        kind = "pkg" if self.is_packaging else "product"
        return f"<PMC {self.product_id} {self.material_type} {kind} {self.weight_per_unit_kg}kg/unit>"


class MonthlySalesVolume(UUIDPrimaryKeyMixin, CustomerScopedMixin, TimestampMixin, Base):
    """Units sold for a product in a given year/month.

    Combined with ProductMaterialComposition, this drives automatic obligation
    calculation without requiring manual weight uploads.
    """

    __tablename__ = "monthly_sales_volumes"
    __table_args__ = (
        UniqueConstraint("customer_id", "product_id", "year", "month", name="uq_msv_customer_product_period"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    units_sold: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # api / csv / manual
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    product: Mapped["Product"] = relationship("Product", back_populates="volumes")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<MonthlySalesVolume {self.product_id} {self.year}-{self.month:02d} {self.units_sold} units>"
