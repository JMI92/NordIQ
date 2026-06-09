"""Product and product weight endpoints — list, upload CSV."""

from __future__ import annotations

import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nordiq.api.dependencies import get_current_user
from nordiq.core.database import get_db
from nordiq.ingestion.base import DataSourceConfig
from nordiq.ingestion.csv_ingestor import CSVIngestor
from nordiq.models.enums import DataRecordSource, MaterialType, ProductCategory
from nordiq.models.product import Product, ProductWeight
from nordiq.models.user import User

router = APIRouter()

# Standard field mapping used for direct CSV uploads (column names are fixed)
UPLOAD_CSV_MAPPING = {
    "external_product_id": "external_product_id",
    "description": "description",
    "product_category": "product_category",
    "weight_kg": "weight_kg",
    "material_type": "material_type",
    "reporting_period_start": "reporting_period_start",
    "reporting_period_end": "reporting_period_end",
}


class ProductResponse(BaseModel):
    id: uuid.UUID
    external_product_id: str
    description: str
    product_category: str
    hs_code: str | None
    weight_count: int

    class Config:
        from_attributes = True


class ProductWeightResponse(BaseModel):
    id: uuid.UUID
    material_type: str
    weight_kg: str  # string to avoid float serialisation issues
    reporting_period_start: str
    reporting_period_end: str
    source: str

    class Config:
        from_attributes = True


class CSVUploadResponse(BaseModel):
    imported: int
    errors: int
    error_details: list[dict]


@router.get("")
async def list_products(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[ProductResponse]:
    result = await db.execute(
        select(Product)
        .where(Product.customer_id == current_user.customer_id)
        .order_by(Product.external_product_id)
        .limit(limit)
        .offset(offset)
    )
    products = result.scalars().all()

    # Count weights per product in one query
    from sqlalchemy import func
    weight_counts_result = await db.execute(
        select(ProductWeight.product_id, func.count().label("cnt"))
        .where(ProductWeight.customer_id == current_user.customer_id)
        .group_by(ProductWeight.product_id)
    )
    weight_counts = {row.product_id: row.cnt for row in weight_counts_result}

    return [
        ProductResponse(
            id=p.id,
            external_product_id=p.external_product_id,
            description=p.description,
            product_category=p.product_category,
            hs_code=p.hs_code,
            weight_count=weight_counts.get(p.id, 0),
        )
        for p in products
    ]


@router.get("/{product_id}/weights")
async def list_product_weights(
    product_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProductWeightResponse]:
    # Verify product belongs to customer
    prod_result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.customer_id == current_user.customer_id,
        )
    )
    if prod_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    result = await db.execute(
        select(ProductWeight)
        .where(
            ProductWeight.product_id == product_id,
            ProductWeight.customer_id == current_user.customer_id,
        )
        .order_by(ProductWeight.reporting_period_start.desc())
    )
    weights = result.scalars().all()
    return [
        ProductWeightResponse(
            id=w.id,
            material_type=w.material_type,
            weight_kg=str(w.weight_kg),
            reporting_period_start=w.reporting_period_start.isoformat(),
            reporting_period_end=w.reporting_period_end.isoformat(),
            source=w.source,
        )
        for w in weights
    ]


@router.post("/upload-csv", status_code=status.HTTP_200_OK)
async def upload_products_csv(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CSVUploadResponse:
    """Upload a CSV file with product weight records.

    Expected columns (exact names, case-sensitive):
    external_product_id, description, product_category, weight_kg,
    material_type, reporting_period_start, reporting_period_end
    """
    content = (await file.read()).decode("utf-8")
    config = DataSourceConfig(
        source_type="csv",
        connection_config={"content": content},
        field_mapping=UPLOAD_CSV_MAPPING,
    )

    result = CSVIngestor().fetch_with_errors(config)
    error_details = [
        {"row": e.row_number, "errors": e.errors, "raw": e.raw_row}
        for e in result.row_errors
    ]

    for record in result.records:
        # Upsert product
        prod_result = await db.execute(
            select(Product).where(
                Product.customer_id == current_user.customer_id,
                Product.external_product_id == record.external_product_id,
            )
        )
        product = prod_result.scalar_one_or_none()
        if product is None:
            product = Product(
                customer_id=current_user.customer_id,
                external_product_id=record.external_product_id,
                description=record.description,
                product_category=record.product_category,
            )
            db.add(product)
            await db.flush()

        # Add weight record
        weight = ProductWeight(
            customer_id=current_user.customer_id,
            product_id=product.id,
            weight_kg=record.weight_kg,
            material_type=record.material_type,
            reporting_period_start=record.reporting_period_start,
            reporting_period_end=record.reporting_period_end,
            source=DataRecordSource.CSV,
        )
        db.add(weight)

    await db.flush()

    return CSVUploadResponse(
        imported=result.success_count,
        errors=result.error_count,
        error_details=error_details,
    )
