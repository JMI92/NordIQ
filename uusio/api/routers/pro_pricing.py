"""PRO pricing and margin settings endpoints (admin only)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user, get_db
from uusio.models.pro_pricing import MarginSettings, PRoPricing
from uusio.models.user import User

router = APIRouter()

SERVICE_FEE_EUR = Decimal("30.00")


def _require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    from fastapi import status
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


AdminUser = Annotated[User, Depends(_require_admin)]


# ── Pricing ──────────────────────────────────────────────────────────────────


def _pricing_out(p: PRoPricing) -> dict:
    return {
        "id": str(p.id),
        "pro_id": str(p.pro_id),
        "waste_stream": p.waste_stream,
        "fee_type": p.fee_type,
        "amount": float(p.amount),
        "currency": p.currency,
        "effective_date": p.effective_date.isoformat(),
        "is_active": p.is_active,
        "notes": p.notes,
        "created_at": p.created_at.isoformat(),
    }


class PricingCreate(BaseModel):
    pro_id: uuid.UUID
    waste_stream: str
    fee_type: str  # registration / annual / material
    amount: Decimal
    currency: str = "EUR"
    effective_date: date
    notes: str | None = None


class PricingUpdate(BaseModel):
    amount: Decimal | None = None
    effective_date: date | None = None
    is_active: bool | None = None
    notes: str | None = None


@router.get("/pricing")
async def list_pricing(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    pro_id: uuid.UUID | None = Query(None),
    waste_stream: str | None = Query(None),
    fee_type: str | None = Query(None),
):
    q = select(PRoPricing).order_by(PRoPricing.created_at.desc())
    if pro_id:
        q = q.where(PRoPricing.pro_id == pro_id)
    if waste_stream:
        q = q.where(PRoPricing.waste_stream == waste_stream)
    if fee_type:
        q = q.where(PRoPricing.fee_type == fee_type)
    rows = (await db.execute(q)).scalars().all()
    return [_pricing_out(p) for p in rows]


@router.post("/pricing", status_code=201)
async def create_pricing(
    body: PricingCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    p = PRoPricing(
        pro_id=body.pro_id,
        waste_stream=body.waste_stream,
        fee_type=body.fee_type,
        amount=body.amount,
        currency=body.currency,
        effective_date=body.effective_date,
        notes=body.notes,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _pricing_out(p)


@router.patch("/pricing/{pricing_id}")
async def update_pricing(
    pricing_id: uuid.UUID,
    body: PricingUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    p = (await db.execute(select(PRoPricing).where(PRoPricing.id == pricing_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pricing entry not found")
    if body.amount is not None:
        p.amount = body.amount
    if body.effective_date is not None:
        p.effective_date = body.effective_date
    if body.is_active is not None:
        p.is_active = body.is_active
    if body.notes is not None:
        p.notes = body.notes
    await db.commit()
    await db.refresh(p)
    return _pricing_out(p)


@router.delete("/pricing/{pricing_id}", status_code=204)
async def delete_pricing(
    pricing_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    p = (await db.execute(select(PRoPricing).where(PRoPricing.id == pricing_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pricing entry not found")
    await db.delete(p)
    await db.commit()


# ── Margin settings ───────────────────────────────────────────────────────────


def _margin_out(m: MarginSettings) -> dict:
    return {
        "id": str(m.id),
        "pro_id": str(m.pro_id) if m.pro_id else None,
        "margin_percentage": float(m.margin_percentage),
        "effective_date": m.effective_date.isoformat(),
        "notes": m.notes,
        "created_at": m.created_at.isoformat(),
    }


class MarginCreate(BaseModel):
    pro_id: uuid.UUID | None = None  # None = global default
    margin_percentage: Decimal
    effective_date: date
    notes: str | None = None


@router.get("/margin-settings")
async def list_margins(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (await db.execute(select(MarginSettings).order_by(MarginSettings.effective_date.desc()))).scalars().all()
    return [_margin_out(m) for m in rows]


@router.post("/margin-settings", status_code=201)
async def create_margin(
    body: MarginCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    m = MarginSettings(
        pro_id=body.pro_id,
        margin_percentage=body.margin_percentage,
        effective_date=body.effective_date,
        notes=body.notes,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return _margin_out(m)


@router.delete("/margin-settings/{margin_id}", status_code=204)
async def delete_margin(
    margin_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    m = (await db.execute(select(MarginSettings).where(MarginSettings.id == margin_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Margin setting not found")
    await db.delete(m)
    await db.commit()


# ── Customer-facing pricing view ─────────────────────────────────────────────


async def _get_margin_for_pro(db: AsyncSession, pro_id: uuid.UUID) -> Decimal:
    """Return the active margin % for a PRO (PRO-specific or global fallback)."""
    today = date.today()
    # PRO-specific first
    row = (
        await db.execute(
            select(MarginSettings)
            .where(MarginSettings.pro_id == pro_id, MarginSettings.effective_date <= today)
            .order_by(MarginSettings.effective_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row:
        return row.margin_percentage
    # Global fallback
    row = (
        await db.execute(
            select(MarginSettings)
            .where(MarginSettings.pro_id.is_(None), MarginSettings.effective_date <= today)
            .order_by(MarginSettings.effective_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.margin_percentage if row else Decimal("15.00")


@router.get("/customer-pricing")
async def get_customer_pricing(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pro_id: uuid.UUID | None = Query(None),
):
    """Return pricing visible to the customer — margin applied to material fees only."""
    from uusio.models.pro_registry import CustomerPRORegistration

    # Find customer's active PRO registrations
    q = select(CustomerPRORegistration).where(
        CustomerPRORegistration.customer_id == current_user.customer_id,
        CustomerPRORegistration.status == "active",
    )
    if pro_id:
        q = q.where(CustomerPRORegistration.pro_id == pro_id)
    registrations = (await db.execute(q)).scalars().all()

    today = date.today()
    result = []
    for reg in registrations:
        margin_pct = await _get_margin_for_pro(db, reg.pro_id)
        pricing_rows = (
            await db.execute(
                select(PRoPricing)
                .where(
                    PRoPricing.pro_id == reg.pro_id,
                    PRoPricing.is_active == True,  # noqa: E712
                    PRoPricing.effective_date <= today,
                )
                .order_by(PRoPricing.waste_stream, PRoPricing.fee_type, PRoPricing.effective_date.desc())
            )
        ).scalars().all()

        seen = set()
        for p in pricing_rows:
            key = (p.waste_stream, p.fee_type)
            if key in seen:
                continue
            seen.add(key)

            if p.fee_type == "material":
                displayed_amount = p.amount * (1 + margin_pct / 100)
            else:
                displayed_amount = p.amount

            result.append({
                "pro_id": str(reg.pro_id),
                "waste_stream": p.waste_stream,
                "fee_type": p.fee_type,
                "amount": round(float(displayed_amount), 4),
                "currency": p.currency,
                "effective_date": p.effective_date.isoformat(),
                "service_fee_per_invoice": float(SERVICE_FEE_EUR) if p.fee_type == "material" else None,
            })

    return result
