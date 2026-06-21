"""Product material composition and monthly sales volume endpoints."""

import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from uusio.api.dependencies import get_current_user, get_db
from uusio.models.product import Product
from uusio.models.volumes import MonthlySalesVolume, ProductMaterialComposition
from uusio.models.user import User

router = APIRouter()


def _comp_dict(c: ProductMaterialComposition) -> dict:
    return {
        "id": str(c.id),
        "product_id": str(c.product_id),
        "material_type": c.material_type,
        "is_packaging": c.is_packaging,
        "weight_per_unit_kg": float(c.weight_per_unit_kg),
        "packaging_stream": c.packaging_stream,
        "notes": c.notes,
    }


def _vol_dict(v: MonthlySalesVolume) -> dict:
    return {
        "id": str(v.id),
        "customer_id": str(v.customer_id),
        "product_id": str(v.product_id),
        "year": v.year,
        "month": v.month,
        "units_sold": float(v.units_sold),
        "source": v.source,
        "created_at": v.created_at.isoformat(),
    }


# -------------------------------------------------------------------------
# Material composition (per product)
# -------------------------------------------------------------------------

class CompositionUpsert(BaseModel):
    material_type: str
    is_packaging: bool = True
    weight_per_unit_kg: Decimal
    packaging_stream: str | None = None
    notes: str | None = None


@router.get("/products/{product_id}/composition")
async def get_composition(
    product_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (await db.execute(
        select(ProductMaterialComposition)
        .where(ProductMaterialComposition.product_id == product_id)
        .order_by(ProductMaterialComposition.is_packaging.desc(), ProductMaterialComposition.material_type)
    )).scalars().all()
    return [_comp_dict(r) for r in rows]


@router.put("/products/{product_id}/composition", status_code=200)
async def upsert_composition(
    product_id: uuid.UUID,
    body: list[CompositionUpsert],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Replace the full material composition list for a product."""
    # Verify product belongs to this customer
    product = (await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.customer_id == current_user.customer_id,
        )
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Delete existing compositions and replace
    existing = (await db.execute(
        select(ProductMaterialComposition).where(ProductMaterialComposition.product_id == product_id)
    )).scalars().all()
    for e in existing:
        await db.delete(e)

    new_comps = [
        ProductMaterialComposition(
            product_id=product_id,
            material_type=item.material_type,
            is_packaging=item.is_packaging,
            weight_per_unit_kg=item.weight_per_unit_kg,
            packaging_stream=item.packaging_stream,
            notes=item.notes,
        )
        for item in body
    ]
    db.add_all(new_comps)
    await db.commit()
    return [_comp_dict(c) for c in new_comps]


# -------------------------------------------------------------------------
# Monthly sales volumes
# -------------------------------------------------------------------------

class VolumeUpsert(BaseModel):
    product_id: uuid.UUID
    year: int
    month: int
    units_sold: Decimal
    source: str = "manual"


@router.get("/volumes")
async def list_volumes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int | None = Query(None),
    month: int | None = Query(None),
):
    q = select(MonthlySalesVolume).where(
        MonthlySalesVolume.customer_id == current_user.customer_id
    ).order_by(MonthlySalesVolume.year.desc(), MonthlySalesVolume.month.desc())
    if year:
        q = q.where(MonthlySalesVolume.year == year)
    if month:
        q = q.where(MonthlySalesVolume.month == month)
    rows = (await db.execute(q)).scalars().all()
    return [_vol_dict(r) for r in rows]


@router.post("/volumes", status_code=201)
async def upsert_volume(
    body: VolumeUpsert,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify product belongs to this customer
    product = (await db.execute(
        select(Product).where(Product.id == body.product_id, Product.customer_id == current_user.customer_id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (await db.execute(
        select(MonthlySalesVolume).where(
            MonthlySalesVolume.customer_id == current_user.customer_id,
            MonthlySalesVolume.product_id == body.product_id,
            MonthlySalesVolume.year == body.year,
            MonthlySalesVolume.month == body.month,
        )
    )).scalar_one_or_none()

    if existing:
        existing.units_sold = body.units_sold
        existing.source = body.source
        await db.commit()
        await db.refresh(existing)
        return _vol_dict(existing)
    else:
        vol = MonthlySalesVolume(
            customer_id=current_user.customer_id,
            product_id=body.product_id,
            year=body.year,
            month=body.month,
            units_sold=body.units_sold,
            source=body.source,
        )
        db.add(vol)
        await db.commit()
        await db.refresh(vol)
        return _vol_dict(vol)


@router.post("/volumes/upload-csv")
async def upload_volumes_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Upload CSV/Excel with columns: sku, year, month, units_sold.

    Upserts all rows. Returns count of rows processed.
    """
    import pandas as pd  # noqa: PLC0415

    content = await file.read()
    fname = file.filename or ""
    try:
        if fname.endswith(".xlsx") or fname.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")

    required = {"sku", "year", "month", "units_sold"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}. Required: sku, year, month, units_sold")

    df.columns = df.columns.str.lower()

    # Load all customer products indexed by SKU
    products = (await db.execute(
        select(Product).where(Product.customer_id == current_user.customer_id)
    )).scalars().all()
    sku_map = {p.external_product_id: p.id for p in products}

    processed, skipped = 0, 0
    for _, row in df.iterrows():
        sku = str(row["sku"]).strip()
        if sku not in sku_map:
            skipped += 1
            continue
        product_id = sku_map[sku]
        year, month = int(row["year"]), int(row["month"])
        units = Decimal(str(row["units_sold"]))

        existing = (await db.execute(
            select(MonthlySalesVolume).where(
                MonthlySalesVolume.customer_id == current_user.customer_id,
                MonthlySalesVolume.product_id == product_id,
                MonthlySalesVolume.year == year,
                MonthlySalesVolume.month == month,
            )
        )).scalar_one_or_none()

        if existing:
            existing.units_sold = units
            existing.source = "csv"
        else:
            db.add(MonthlySalesVolume(
                customer_id=current_user.customer_id,
                product_id=product_id,
                year=year, month=month,
                units_sold=units,
                source="csv",
            ))
        processed += 1

    await db.commit()
    return {"processed": processed, "skipped_unknown_sku": skipped}


# -------------------------------------------------------------------------
# Auto-calculate totals from volumes + composition
# -------------------------------------------------------------------------

@router.post("/volumes/calculate")
async def calculate_from_volumes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(...),
    month: int = Query(...),
):
    """Aggregate material weights for a given month from volumes × composition.

    Returns a breakdown by product_category and material_type ready to feed
    into the EPR calculation engine.
    """
    vols = (await db.execute(
        select(MonthlySalesVolume)
        .options(selectinload(MonthlySalesVolume.product))
        .where(
            MonthlySalesVolume.customer_id == current_user.customer_id,
            MonthlySalesVolume.year == year,
            MonthlySalesVolume.month == month,
        )
    )).scalars().all()

    if not vols:
        return {"year": year, "month": month, "totals": [], "message": "No sales volumes found for this period"}

    # Accumulate: (product_category, material_type, is_packaging) -> total_kg
    from collections import defaultdict
    totals: dict = defaultdict(Decimal)

    for vol in vols:
        product = vol.product
        if not product:
            continue
        comps = (await db.execute(
            select(ProductMaterialComposition).where(ProductMaterialComposition.product_id == product.id)
        )).scalars().all()
        for comp in comps:
            key = (product.product_category, comp.material_type, comp.is_packaging)
            totals[key] += Decimal(str(vol.units_sold)) * comp.weight_per_unit_kg

    period_start = date(year, month, 1)
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    period_end = date(year, month, last_day)

    result = []
    for (category, material, is_pkg), total_kg in sorted(totals.items()):
        result.append({
            "product_category": category,
            "material_type": material,
            "is_packaging": is_pkg,
            "total_kg": float(total_kg),
        })

    return {
        "year": year,
        "month": month,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "totals": result,
    }
