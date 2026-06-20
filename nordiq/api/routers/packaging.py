"""Packaging component (bill-of-materials) endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nordiq.api.dependencies import get_current_user
from nordiq.core.database import get_db
from nordiq.models.packaging import PackagingComponent
from nordiq.models.user import User

router = APIRouter()


class PackagingComponentCreate(BaseModel):
    sku: str
    product_name: str | None = None
    component_name: str
    material_type: str
    packaging_stream: str = "household"
    weight_grams: float
    is_recyclable: bool = False
    recyclability_class: str | None = None
    is_single_use_plastic: bool = False
    is_reusable: bool = False
    valid_from: str | None = None
    valid_to: str | None = None


class PackagingComponentResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    sku: str
    product_name: str | None
    component_name: str
    material_type: str
    packaging_stream: str
    weight_grams: float
    is_recyclable: bool
    recyclability_class: str | None
    is_single_use_plastic: bool
    is_reusable: bool
    is_active: bool

    class Config:
        from_attributes = True


@router.get("", response_model=list[PackagingComponentResponse])
async def list_components(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    sku: str | None = Query(default=None),
):
    stmt = select(PackagingComponent).where(
        PackagingComponent.customer_id == current_user.customer_id,
        PackagingComponent.is_active == True,  # noqa: E712
    )
    if sku:
        stmt = stmt.where(PackagingComponent.sku == sku)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=PackagingComponentResponse, status_code=status.HTTP_201_CREATED)
async def create_component(
    body: PackagingComponentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from decimal import Decimal
    from datetime import date
    comp = PackagingComponent(
        customer_id=current_user.customer_id,
        sku=body.sku,
        product_name=body.product_name,
        component_name=body.component_name,
        material_type=body.material_type,
        packaging_stream=body.packaging_stream,
        weight_grams=Decimal(str(body.weight_grams)),
        is_recyclable=body.is_recyclable,
        recyclability_class=body.recyclability_class,
        is_single_use_plastic=body.is_single_use_plastic,
        is_reusable=body.is_reusable,
        valid_from=date.fromisoformat(body.valid_from) if body.valid_from else None,
        valid_to=date.fromisoformat(body.valid_to) if body.valid_to else None,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@router.get("/{component_id}", response_model=PackagingComponentResponse)
async def get_component(
    component_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(PackagingComponent).where(
            PackagingComponent.id == component_id,
            PackagingComponent.customer_id == current_user.customer_id,
        )
    )
    comp = result.scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Component not found")
    return comp


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_component(
    component_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(PackagingComponent).where(
            PackagingComponent.id == component_id,
            PackagingComponent.customer_id == current_user.customer_id,
        )
    )
    comp = result.scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Component not found")
    comp.is_active = False
    await db.commit()
