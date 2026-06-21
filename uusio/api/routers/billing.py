"""Invoice / billing endpoints (admin only)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user, get_db
from uusio.models.billing import Invoice
from uusio.models.user import User

router = APIRouter()


def _require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    from fastapi import status
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


AdminUser = Annotated[User, Depends(_require_admin)]


def _invoice_dict(inv: Invoice) -> dict:
    return {
        "id": str(inv.id),
        "customer_id": str(inv.customer_id),
        "invoice_number": inv.invoice_number,
        "amount": float(inv.amount),
        "currency": inv.currency,
        "status": inv.status,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "sent_at": inv.sent_at.isoformat() if inv.sent_at else None,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "notes": inv.notes,
        "line_items": inv.line_items or [],
        "created_at": inv.created_at.isoformat(),
    }


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    invoice_number: str
    amount: Decimal
    currency: str = "EUR"
    due_date: str | None = None
    notes: str | None = None
    line_items: list | None = None


class InvoiceUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    paid_at: str | None = None


@router.get("")
async def list_invoices(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    customer_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
):
    q = select(Invoice).order_by(Invoice.created_at.desc())
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)
    if status:
        q = q.where(Invoice.status == status)
    rows = (await db.execute(q)).scalars().all()
    return [_invoice_dict(i) for i in rows]


@router.post("", status_code=201)
async def create_invoice(
    body: InvoiceCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from datetime import date
    inv = Invoice(
        customer_id=body.customer_id,
        invoice_number=body.invoice_number,
        amount=body.amount,
        currency=body.currency,
        notes=body.notes,
        line_items=body.line_items,
        status="draft",
    )
    if body.due_date:
        inv.due_date = date.fromisoformat(body.due_date)
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return _invoice_dict(inv)


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    inv = (await db.execute(select(Invoice).where(Invoice.id == invoice_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if body.status is not None:
        inv.status = body.status
        if body.status == "sent" and inv.sent_at is None:
            inv.sent_at = datetime.now(timezone.utc)
        if body.status == "paid" and inv.paid_at is None:
            inv.paid_at = datetime.now(timezone.utc)
    if body.notes is not None:
        inv.notes = body.notes
    if body.paid_at is not None:
        inv.paid_at = datetime.fromisoformat(body.paid_at)
    await db.commit()
    await db.refresh(inv)
    return _invoice_dict(inv)


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    inv = (await db.execute(select(Invoice).where(Invoice.id == invoice_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await db.delete(inv)
    await db.commit()
