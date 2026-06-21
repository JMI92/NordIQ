"""Portal self-service: PRO registrations, reporting calendar, report archive, documents."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from uusio.api.dependencies import get_current_user, get_db
from uusio.models.obligation import EPRObligation, ReportingDeadline
from uusio.models.pro_registry import CustomerPRORegistration
from uusio.models.submission import PROSubmission
from uusio.models.user import User

router = APIRouter()


@router.get("/summary")
async def portal_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    regs = (await db.execute(
        select(CustomerPRORegistration)
        .options(selectinload(CustomerPRORegistration.pro))
        .where(
            CustomerPRORegistration.customer_id == current_user.customer_id,
            CustomerPRORegistration.status == "active",
        )
    )).scalars().all()

    obligations = (await db.execute(
        select(EPRObligation).where(EPRObligation.customer_id == current_user.customer_id)
    )).scalars().all()

    submissions = (await db.execute(
        select(PROSubmission).where(PROSubmission.customer_id == current_user.customer_id)
    )).scalars().all()

    active_countries = sorted({r.pro.country_code for r in regs if r.pro})

    return {
        "active_pro_count": len(regs),
        "active_countries": active_countries,
        "total_obligations": len(obligations),
        "total_submissions": len(submissions),
        "successful_submissions": sum(1 for s in submissions if s.status == "success"),
    }


@router.get("/registrations")
async def my_registrations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    regs = (await db.execute(
        select(CustomerPRORegistration)
        .options(selectinload(CustomerPRORegistration.pro))
        .where(CustomerPRORegistration.customer_id == current_user.customer_id)
        .order_by(CustomerPRORegistration.status)
    )).scalars().all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "registration_number": r.registration_number,
            "contract_start": r.contract_start.isoformat() if r.contract_start else None,
            "contract_end": r.contract_end.isoformat() if r.contract_end else None,
            "notes": r.notes,
            "pro": {
                "id": str(r.pro.id),
                "name": r.pro.name,
                "country_code": r.pro.country_code,
                "category": r.pro.category,
                "pro_key": r.pro.pro_key,
                "portal_url": r.pro.portal_url,
                "contact_name": r.pro.contact_name,
                "contact_email": r.pro.contact_email,
                "reporting_deadline_notes": r.pro.reporting_deadline_notes,
            } if r.pro else None,
        }
        for r in regs
    ]


@router.get("/reporting-calendar")
async def reporting_calendar(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Upcoming reporting deadlines for this customer's active PRO registrations."""
    from datetime import date, timedelta

    regs = (await db.execute(
        select(CustomerPRORegistration)
        .options(selectinload(CustomerPRORegistration.pro))
        .where(
            CustomerPRORegistration.customer_id == current_user.customer_id,
            CustomerPRORegistration.status == "active",
        )
    )).scalars().all()

    if not regs:
        return []

    today = date.today()
    horizon = today.replace(year=today.year + 1)  # look 12 months ahead

    # Collect (country_code, category, pro_key) combos from active registrations
    pro_by_key: dict = {}
    active_combos: list[tuple[str, str, str]] = []
    for reg in regs:
        if reg.pro:
            active_combos.append((reg.pro.country_code, reg.pro.category, reg.pro.pro_key))
            pro_by_key[reg.pro.pro_key] = reg.pro

    # Pull deadlines for matching countries/categories within horizon
    active_countries = [c for c, _, _ in active_combos]
    deadlines = (await db.execute(
        select(ReportingDeadline)
        .where(
            ReportingDeadline.submission_deadline >= today,
            ReportingDeadline.submission_deadline <= horizon,
            ReportingDeadline.country_code.in_(active_countries),
        )
        .order_by(ReportingDeadline.submission_deadline)
    )).scalars().all()

    # Match deadlines to customer's specific PRO registrations
    result = []
    for dl in deadlines:
        # Find matching registration (same country + category mapping)
        matched_reg = next(
            (r for r in regs if r.pro and r.pro.country_code == dl.country_code
             and r.pro.pro_key == dl.pro_id),
            None,
        )
        if not matched_reg:
            # Also check by country_code alone if category matches
            matched_reg = next(
                (r for r in regs if r.pro and r.pro.country_code == dl.country_code),
                None,
            )
        if not matched_reg:
            continue

        days_until = (dl.submission_deadline - today).days
        if days_until <= 7:
            urgency = "critical"
        elif days_until <= 30:
            urgency = "warning"
        else:
            urgency = "ok"

        # Check if obligation exists for this period
        obligation = (await db.execute(
            select(EPRObligation)
            .where(
                EPRObligation.customer_id == current_user.customer_id,
                EPRObligation.country_code == dl.country_code,
                EPRObligation.reporting_period_start == dl.reporting_period_start,
                EPRObligation.reporting_period_end == dl.reporting_period_end,
            )
            .limit(1)
        )).scalar_one_or_none()

        pro = matched_reg.pro
        result.append({
            "deadline_id": str(dl.id),
            "country_code": dl.country_code,
            "product_category": dl.product_category,
            "pro_id": dl.pro_id,
            "pro_name": pro.name if pro else dl.pro_id,
            "pro_portal_url": pro.portal_url if pro else None,
            "reporting_period_start": dl.reporting_period_start.isoformat(),
            "reporting_period_end": dl.reporting_period_end.isoformat(),
            "submission_deadline": dl.submission_deadline.isoformat(),
            "days_until_deadline": days_until,
            "urgency": urgency,
            "obligation_status": obligation.status if obligation else None,
            "obligation_id": str(obligation.id) if obligation else None,
            "notes": dl.notes,
        })

    return result


@router.get("/reports")
async def my_reports(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    subs = (await db.execute(
        select(PROSubmission)
        .options(selectinload(PROSubmission.obligation))
        .where(PROSubmission.customer_id == current_user.customer_id)
        .order_by(PROSubmission.created_at.desc())
    )).scalars().all()

    result = []
    for s in subs:
        download_url = None
        if s.report_file_path:
            try:
                from uusio.storage.s3 import presigned_url
                download_url = presigned_url(s.report_file_path, expires_in=3600)
            except Exception:
                pass
        obl = s.obligation
        result.append({
            "id": str(s.id),
            "pro_id": s.pro_id,
            "status": s.status,
            "submission_method": s.submission_method,
            "submitted_at": s.created_at.isoformat(),
            "report_file_path": s.report_file_path,
            "download_url": download_url,
            "error_message": s.error_message,
            "obligation": {
                "country_code": obl.country_code if obl else None,
                "product_category": obl.product_category if obl else None,
                "period_start": obl.reporting_period_start.isoformat() if obl else None,
                "period_end": obl.reporting_period_end.isoformat() if obl else None,
                "total_weight_kg": float(obl.total_weight_kg) if obl and obl.total_weight_kg else None,
                "fee_amount": float(obl.fee_amount) if obl and obl.fee_amount else None,
                "currency": obl.currency if obl else None,
            } if obl else None,
        })
    return result


@router.get("/files")
async def list_my_files(
    current_user: Annotated[User, Depends(get_current_user)],
    folder: str | None = Query(None),
):
    from uusio.storage.s3 import customer_prefix, list_objects, presigned_url
    prefix = customer_prefix(str(current_user.customer_id), folder or "")
    files = list_objects(prefix)
    result = []
    for f in files:
        try:
            url = presigned_url(f["s3_uri"], expires_in=3600)
        except Exception:
            url = None
        result.append({**f, "download_url": url})
    return result


@router.post("/files/upload", status_code=201)
async def upload_my_file(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    folder: str = Query("contracts"),
):
    import re
    from uusio.storage.s3 import customer_prefix, upload_bytes
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename or "upload")
    key = f"{customer_prefix(str(current_user.customer_id), folder)}{safe_name}"
    data = await file.read()
    uri = upload_bytes(data, key, file.content_type or "application/octet-stream")
    return {"s3_uri": uri, "filename": safe_name, "folder": folder, "size": len(data)}
