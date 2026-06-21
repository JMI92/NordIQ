"""Product model — updated to include composition and volume relationships."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uusio.core.database import Base
from uusio.models.enums import DataRecordSource, MaterialType, ProductCategory
from uusio.models.mixins import CustomerScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, CustomerScopedMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("customer_id", "external_product_id", name="uq_product_customer_ext_id"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    external_product_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    product_category: Mapped[ProductCategory] = mapped_column(String(50), nullable=False, index=True)
    hs_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="products")  # type: ignore[name-defined]
    weights: Mapped[list["ProductWeight"]] = relationship(
        "ProductWeight", back_populates="product", cascade="all, delete-orphan"
    )
    compositions: Mapped[list["ProductMaterialComposition"]] = relationship(  # type: ignore[name-defined]
        "ProductMaterialComposition", back_populates="product", cascade="all, delete-orphan"
    )
    volumes: Mapped[list["MonthlySalesVolume"]] = relationship(  # type: ignore[name-defined]
        "MonthlySalesVolume", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product {self.external_product_id} ({self.product_category})>"


class ProductWeight(UUIDPrimaryKeyMixin, CustomerScopedMixin, TimestampMixin, Base):
    """Legacy total-weight record per period (kept for backwards compatibility)."""

    __tablename__ = "product_weights"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    weight_kg: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    material_type: Mapped[MaterialType] = mapped_column(String(50), nullable=False, index=True)
    reporting_period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reporting_period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[DataRecordSource] = mapped_column(String(50), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="weights")
    customer: Mapped["Customer"] = relationship("Customer")  # type: ignore[name-defined]
