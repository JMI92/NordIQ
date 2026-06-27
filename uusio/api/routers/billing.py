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
from uusio.models.billing import Invoice, PROInvoice
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
        "invoice_type": inv.invoice_type,
        "amount": float(inv.amount),
        "service_fee": float(inv.service_fee),
        "currency": inv.currency,
        "status": inv.status,
        "period_start": inv.period_start.isoformat() if inv.period_start else None,
        "period_end": inv.period_end.isoformat() if inv.period_end else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "sent_at": inv.sent_at.isoformat() if inv.sent_at else None,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "notes": inv.notes,
        "line_items": inv.line_items or [],
        "accounting_ref": inv.accounting_ref,
        "accounting_exported_at": inv.accounting_exported_at.isoformat() if inv.accounting_exported_at else None,
        "created_at": inv.created_at.isoformat(),
    }


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    invoice_number: str
    invoice_type: str = "manual"
    amount: Decimal
    service_fee: Decimal = Decimal("30.00")
    currency: str = "EUR"
    period_start: str | None = None
    period_end: str | None = None
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
        invoice_type=body.invoice_type,
        amount=body.amount,
        service_fee=body.service_fee,
        currency=body.currency,
        notes=body.notes,
        line_items=body.line_items,
        status="draft",
    )
    if body.due_date:
        inv.due_date = date.fromisoformat(body.due_date)
    if body.period_start:
        inv.period_start = date.fromisoformat(body.period_start)
    if body.period_end:
        inv.period_end = date.fromisoformat(body.period_end)
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


@router.post("/generate/monthly", status_code=202)
async def trigger_monthly_generation(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually trigger monthly invoice generation (runs automatically on 1st of month)."""
    import asyncio
    from uusio.core.database import async_session_factory
    from uusio.scheduler.invoice_generator import generate_monthly_invoices
    asyncio.create_task(generate_monthly_invoices(async_session_factory))
    return {"status": "accepted", "message": "Monthly invoice generation started in background"}


@router.post("/generate/annual", status_code=202)
async def trigger_annual_generation(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Manually trigger annual invoice generation (runs automatically on 1 Jan)."""
    import asyncio
    from uusio.core.database import async_session_factory
    from uusio.scheduler.invoice_generator import generate_annual_invoices
    asyncio.create_task(generate_annual_invoices(async_session_factory))
    return {"status": "accepted", "message": "Annual invoice generation started in background"}


@router.post("/{invoice_id}/export-accounting", status_code=200)
async def export_to_accounting(
    invoice_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Placeholder: export invoice data to accounting software (Procountor/Xero).

    When accounting software is chosen, implement the actual API call here.
    Returns structured invoice data ready for import.
    """
    inv = (await db.execute(select(Invoice).where(Invoice.id == invoice_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Structured export payload — adapt to target accounting software format
    export_payload = {
        "invoice_number": inv.invoice_number,
        "invoice_type": inv.invoice_type,
        "customer_id": str(inv.customer_id),
        "period_start": inv.period_start.isoformat() if inv.period_start else None,
        "period_end": inv.period_end.isoformat() if inv.period_end else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "currency": inv.currency,
        "line_items": inv.line_items or [],
        "total_excl_vat": float(inv.amount),
        "status": "ready_for_accounting",
        "note": "Accounting integration not yet configured. Connect Procountor or Xero to enable automatic export.",
    }

    return export_payload


# ---------------------------------------------------------------------------
# PRO Invoices (incoming — what PROs charge us)
# ---------------------------------------------------------------------------

def _pro_invoice_dict(pi: PROInvoice) -> dict:
    return {
        "id": str(pi.id),
        "pro_id": str(pi.pro_id) if pi.pro_id else None,
        "customer_id": str(pi.customer_id),
        "customer_invoice_id": str(pi.customer_invoice_id) if pi.customer_invoice_id else None,
        "pro_invoice_number": pi.pro_invoice_number,
        "invoice_type": pi.invoice_type,
        "amount": float(pi.amount),
        "currency": pi.currency,
        "period_start": pi.period_start.isoformat() if pi.period_start else None,
        "period_end": pi.period_end.isoformat() if pi.period_end else None,
        "due_date": pi.due_date.isoformat() if pi.due_date else None,
        "status": pi.status,
        "received_at": pi.received_at.isoformat() if pi.received_at else None,
        "paid_at": pi.paid_at.isoformat() if pi.paid_at else None,
        "notes": pi.notes,
        "line_items": pi.line_items or [],
        "created_at": pi.created_at.isoformat(),
    }


class PROInvoiceCreate(BaseModel):
    pro_id: uuid.UUID | None = None
    customer_id: uuid.UUID
    customer_invoice_id: uuid.UUID | None = None
    pro_invoice_number: str | None = None
    invoice_type: str = "monthly"
    amount: Decimal
    currency: str = "EUR"
    period_start: str | None = None
    period_end: str | None = None
    due_date: str | None = None
    received_at: str | None = None
    notes: str | None = None
    line_items: list | None = None


class PROInvoiceUpdate(BaseModel):
    status: str | None = None
    paid_at: str | None = None
    customer_invoice_id: uuid.UUID | None = None
    notes: str | None = None


@router.get("/pro-invoices")
async def list_pro_invoices(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    customer_id: uuid.UUID | None = Query(None),
    pro_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
):
    q = select(PROInvoice).order_by(PROInvoice.created_at.desc())
    if customer_id:
        q = q.where(PROInvoice.customer_id == customer_id)
    if pro_id:
        q = q.where(PROInvoice.pro_id == pro_id)
    if status:
        q = q.where(PROInvoice.status == status)
    rows = (await db.execute(q)).scalars().all()
    return [_pro_invoice_dict(pi) for pi in rows]


@router.post("/pro-invoices", status_code=201)
async def create_pro_invoice(
    body: PROInvoiceCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Record an incoming invoice received from a PRO."""
    from datetime import date
    pi = PROInvoice(
        pro_id=body.pro_id,
        customer_id=body.customer_id,
        customer_invoice_id=body.customer_invoice_id,
        pro_invoice_number=body.pro_invoice_number,
        invoice_type=body.invoice_type,
        amount=body.amount,
        currency=body.currency,
        notes=body.notes,
        line_items=body.line_items,
        status="received",
    )
    if body.period_start:
        pi.period_start = date.fromisoformat(body.period_start)
    if body.period_end:
        pi.period_end = date.fromisoformat(body.period_end)
    if body.due_date:
        pi.due_date = date.fromisoformat(body.due_date)
    if body.received_at:
        pi.received_at = date.fromisoformat(body.received_at)
    db.add(pi)
    await db.commit()
    await db.refresh(pi)
    return _pro_invoice_dict(pi)


@router.patch("/pro-invoices/{pro_invoice_id}")
async def update_pro_invoice(
    pro_invoice_id: uuid.UUID,
    body: PROInvoiceUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    pi = (await db.execute(select(PROInvoice).where(PROInvoice.id == pro_invoice_id))).scalar_one_or_none()
    if not pi:
        raise HTTPException(status_code=404, detail="PRO invoice not found")
    if body.status is not None:
        pi.status = body.status
        if body.status == "paid" and pi.paid_at is None:
            pi.paid_at = datetime.now(timezone.utc)
    if body.customer_invoice_id is not None:
        pi.customer_invoice_id = body.customer_invoice_id
    if body.notes is not None:
        pi.notes = body.notes
    if body.paid_at is not None:
        pi.paid_at = datetime.fromisoformat(body.paid_at)
    await db.commit()
    await db.refresh(pi)
    return _pro_invoice_dict(pi)


# ---------------------------------------------------------------------------
# Margin reconciliation
# ---------------------------------------------------------------------------

EXPECTED_MARGIN_PCT = Decimal("15.00")   # matches MarginSettings default
MARGIN_TOLERANCE_PCT = Decimal("3.00")   # warn if actual margin deviates more than this


@router.get("/reconciliation")
async def margin_reconciliation(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    customer_id: uuid.UUID | None = Query(None),
    period_start: str | None = Query(None),
    period_end: str | None = Query(None),
):
    """Compare outgoing customer invoices vs incoming PRO invoices.

    For material fee invoices (monthly): the margin should be ~12–15%.
    Annual and registration invoices are pass-through (0% margin expected).

    Returns per-customer-period rows with:
      - outgoing_total: what we charged the customer (excl. service fee)
      - incoming_total: what PRO charged us
      - actual_margin_eur: outgoing - incoming
      - actual_margin_pct: actual_margin_eur / outgoing * 100
      - expected_margin_pct: 12% for material fees, 0% for pass-through
      - delta_pct: actual - expected (negative = we're losing money)
      - status: ok | warning | critical
    """
    from datetime import date
    from sqlalchemy import and_

    # Fetch outgoing invoices
    inv_q = select(Invoice)
    if customer_id:
        inv_q = inv_q.where(Invoice.customer_id == customer_id)
    if period_start:
        inv_q = inv_q.where(Invoice.period_start >= date.fromisoformat(period_start))
    if period_end:
        inv_q = inv_q.where(Invoice.period_end <= date.fromisoformat(period_end))
    inv_q = inv_q.where(Invoice.status.notin_(["cancelled"]))
    outgoing = (await db.execute(inv_q)).scalars().all()

    # Fetch incoming PRO invoices
    pro_q = select(PROInvoice)
    if customer_id:
        pro_q = pro_q.where(PROInvoice.customer_id == customer_id)
    if period_start:
        pro_q = pro_q.where(PROInvoice.period_start >= date.fromisoformat(period_start))
    if period_end:
        pro_q = pro_q.where(PROInvoice.period_end <= date.fromisoformat(period_end))
    incoming_rows = (await db.execute(pro_q)).scalars().all()

    # Group outgoing by (customer_id, period_start, period_end, invoice_type)
    out_map: dict[tuple, dict] = {}
    for inv in outgoing:
        key = (str(inv.customer_id), str(inv.period_start), str(inv.period_end), inv.invoice_type)
        if key not in out_map:
            out_map[key] = {"amount": Decimal("0"), "service_fee": Decimal("0"), "ids": []}
        out_map[key]["amount"] += inv.amount
        out_map[key]["service_fee"] += inv.service_fee or Decimal("0")
        out_map[key]["ids"].append(str(inv.id))

    # Group incoming by (customer_id, period_start, period_end, invoice_type)
    in_map: dict[tuple, dict] = {}
    for pi in incoming_rows:
        key = (str(pi.customer_id), str(pi.period_start), str(pi.period_end), pi.invoice_type)
        if key not in in_map:
            in_map[key] = {"amount": Decimal("0"), "ids": []}
        in_map[key]["amount"] += pi.amount
        in_map[key]["ids"].append(str(pi.id))

    all_keys = set(out_map.keys()) | set(in_map.keys())
    rows = []

    for key in sorted(all_keys):
        cid, p_start, p_end, inv_type = key
        out = out_map.get(key, {"amount": Decimal("0"), "service_fee": Decimal("0"), "ids": []})
        inc = in_map.get(key, {"amount": Decimal("0"), "ids": []})

        # Service fee is our fixed charge on top — exclude from margin calc
        outgoing_material = out["amount"] - out["service_fee"]
        incoming_cost = inc["amount"]

        # Annual and registration are pass-through — expected margin = 0
        is_passthrough = inv_type in ("annual", "registration")
        expected_margin = Decimal("0") if is_passthrough else EXPECTED_MARGIN_PCT

        if outgoing_material > 0:
            actual_margin_eur = outgoing_material - incoming_cost
            actual_margin_pct = (actual_margin_eur / outgoing_material * 100).quantize(Decimal("0.01"))
        else:
            actual_margin_eur = Decimal("0") - incoming_cost
            actual_margin_pct = Decimal("0")

        delta = actual_margin_pct - expected_margin

        if is_passthrough:
            # For pass-through, warn if we're charging more than cost
            rec_status = "ok" if abs(delta) <= MARGIN_TOLERANCE_PCT else "warning"
        elif delta < -MARGIN_TOLERANCE_PCT:
            rec_status = "critical"   # actual margin well below expected
        elif abs(delta) <= MARGIN_TOLERANCE_PCT:
            rec_status = "ok"
        else:
            rec_status = "warning"    # margin higher than expected (acceptable but notable)

        rows.append({
            "customer_id": cid,
            "period_start": p_start,
            "period_end": p_end,
            "invoice_type": inv_type,
            "is_passthrough": is_passthrough,
            "outgoing_total": float(out["amount"]),
            "outgoing_material_fee": float(outgoing_material),
            "service_fee_total": float(out["service_fee"]),
            "incoming_pro_cost": float(incoming_cost),
            "actual_margin_eur": float(actual_margin_eur),
            "actual_margin_pct": float(actual_margin_pct),
            "expected_margin_pct": float(expected_margin),
            "delta_pct": float(delta),
            "status": rec_status,
            "outgoing_invoice_ids": out["ids"],
            "incoming_invoice_ids": inc["ids"],
            "missing_pro_invoice": not inc["ids"],
        })

    summary = {
        "total_outgoing": float(sum(Decimal(str(r["outgoing_total"])) for r in rows)),
        "total_incoming": float(sum(Decimal(str(r["incoming_pro_cost"])) for r in rows)),
        "total_margin_eur": float(sum(Decimal(str(r["actual_margin_eur"])) for r in rows)),
        "rows_ok": sum(1 for r in rows if r["status"] == "ok"),
        "rows_warning": sum(1 for r in rows if r["status"] == "warning"),
        "rows_critical": sum(1 for r in rows if r["status"] == "critical"),
        "rows_missing_pro_invoice": sum(1 for r in rows if r["missing_pro_invoice"]),
    }

    return {"summary": summary, "rows": rows}
