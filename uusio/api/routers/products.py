"""Product endpoints — list, bulk upsert with AI classification, CSV upload."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from uusio.api.dependencies import get_current_user
from uusio.core.database import get_db
from uusio.ingestion.base import DataSourceConfig
from uusio.ingestion.csv_ingestor import CSVIngestor
from uusio.models.enums import DataRecordSource
from uusio.models.product import Product, ProductWeight
from uusio.models.user import User
from uusio.models.volumes import ProductMaterialComposition

router = APIRouter()

UPLOAD_CSV_MAPPING = {
    "external_product_id": "external_product_id",
    "description": "description",
    "product_category": "product_category",
    "weight_kg": "weight_kg",
    "material_type": "material_type",
    "reporting_period_start": "reporting_period_start",
    "reporting_period_end": "reporting_period_end",
}


class MaterialIn(BaseModel):
    type: str
    weightKg: float
    isPackaging: bool = False


class ProductIn(BaseModel):
    id: str | None = None
    sku: str
    name: str
    category: str = ""
    description: str = ""
    materials: list[MaterialIn] = []


class BulkUpsertRequest(BaseModel):
    products: list[ProductIn]
    classify: bool = True  # set False to skip AI classification


class MaterialOut(BaseModel):
    type: str
    weightKg: float
    isPackaging: bool
    aiClassified: bool = False


class ProductOut(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    materials: list[MaterialOut]
    aiConfidence: float | None = None
    aiReasoning: str | None = None


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
    weight_kg: str
    reporting_period_start: str
    reporting_period_end: str
    source: str

    class Config:
        from_attributes = True


class CSVUploadResponse(BaseModel):
    imported: int
    errors: int
    error_details: list[dict]


def _product_to_out(
    p: Product,
    ai_confidence: float | None = None,
    ai_reasoning: str | None = None,
) -> ProductOut:
    return ProductOut(
        id=str(p.id),
        sku=p.external_product_id,
        name=p.description,
        category=p.product_category,
        materials=[
            MaterialOut(
                type=c.material_type,
                weightKg=float(c.weight_per_unit_kg),
                isPackaging=c.is_packaging,
                aiClassified=bool(getattr(c, "ai_classified", False)),
            )
            for c in (p.compositions or [])
        ],
        aiConfidence=ai_confidence,
        aiReasoning=ai_reasoning,
    )


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


@router.post("/bulk", response_model=list[ProductOut])
async def bulk_upsert_products(
    body: BulkUpsertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProductOut]:
    """Create or update products with optional AI material classification.

    If a product has no materials and classify=True, Claude classifies it automatically.
    Matches on SKU. Replaces compositions on each upsert.
    """
    # Determine which products need AI classification
    needs_ai = [
        {"sku": p.sku, "name": p.name, "description": p.description or p.name, "category": p.category}
        for p in body.products
        if not p.materials and body.classify
    ]

    ai_results: dict[str, dict] = {}
    if needs_ai:
        from uusio.services.material_classifier import classify_products_batch
        classifications = await classify_products_batch(needs_ai)
        for c in classifications:
            if c["result"]:
                ai_results[c["sku"]] = c["result"]

    results: list[ProductOut] = []

    for item in body.products:
        # Resolve materials: provided by caller OR AI-classified
        ai_data = ai_results.get(item.sku)
        if not item.materials and ai_data:
            resolved_materials = [
                MaterialIn(
                    type=m["material_type"],
                    weightKg=m["weight_per_unit_kg"],
                    isPackaging=m["is_packaging"],
                )
                for m in ai_data.get("materials", [])
            ]
            resolved_category = ai_data.get("category") or item.category
            ai_confidence = ai_data.get("confidence")
            ai_reasoning = ai_data.get("reasoning")
        else:
            resolved_materials = item.materials
            resolved_category = item.category
            ai_confidence = None
            ai_reasoning = None

        # Upsert product
        res = await db.execute(
            select(Product)
            .options(selectinload(Product.compositions))
            .where(
                Product.customer_id == current_user.customer_id,
                Product.external_product_id == item.sku,
            )
        )
        product = res.scalar_one_or_none()

        if product is None:
            product = Product(
                customer_id=current_user.customer_id,
                external_product_id=item.sku,
                description=item.name,
                product_category=resolved_category or "other",
            )
            db.add(product)
            await db.flush()
        else:
            product.description = item.name
            if resolved_category:
                product.product_category = resolved_category
            for c in list(product.compositions):
                await db.delete(c)
            await db.flush()

        # Insert compositions
        for mat in resolved_materials:
            db.add(ProductMaterialComposition(
                product_id=product.id,
                material_type=mat.type,
                weight_per_unit_kg=mat.weightKg,
                is_packaging=mat.isPackaging,
            ))

        await db.flush()

        # Reload with compositions
        res2 = await db.execute(
            select(Product)
            .options(selectinload(Product.compositions))
            .where(Product.id == product.id)
        )
        product = res2.scalar_one()
        results.append(_product_to_out(product, ai_confidence, ai_reasoning))

    return results


@router.get("/{product_id}/weights")
async def list_product_weights(
    product_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProductWeightResponse]:
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
