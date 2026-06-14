"""Packaging bill-of-materials — SKU-level component breakdown."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from nordiq.core.database import Base


class PackagingComponent(Base):
    """One packaging component attached to a product SKU."""

    __tablename__ = "packaging_components"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sku = Column(String(255), nullable=False, index=True)
    product_name = Column(String(500), nullable=True)
    component_name = Column(String(255), nullable=False)
    material_type = Column(String(50), nullable=False)
    packaging_stream = Column(String(20), nullable=False, server_default="household")
    weight_grams = Column(Numeric(12, 4), nullable=False)
    is_recyclable = Column(Boolean, nullable=False, server_default="false")
    recyclability_class = Column(String(50), nullable=True)
    is_single_use_plastic = Column(Boolean, nullable=False, server_default="false")
    is_reusable = Column(Boolean, nullable=False, server_default="false")
    is_active = Column(Boolean, nullable=False, server_default="true")
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
