"""Customer self-service portal endpoints.

Every authenticated user can see their own customer's data:
- Active PRO registrations
- Reporting archive (submissions + presigned download URLs)
- Customer document files in S3
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from uusio.api.dependencies import get_current_user, get_db
from uusio.models.customer import Customer
from uusio.models.obligation import EPRObligation
from uusio.models.pro_registry import CustomerPRORegistration
from uusio.models.submission import PROSubmission
from uusio.models.user import User

router = APIRouter()


@router.get("/summary")
async def portal_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """High-level summary for the customer portal home."""
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

    active_countries = list({r.pro.country_code for r in regs if r.pro})
    active_countries.sort()

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
    """Customer's own PRO registrations."""
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


@router.get("/reports")
async def my_reports(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Reporting archive: all submissions with presigned download links."""
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
                "period_start": obl.period_start.isoformat() if obl and obl.period_start else None,
                "period_end": obl.period_end.isoformat() if obl and obl.period_end else None,
                "total_weight_kg": float(obl.total_weight_kg) if obl and obl.total_weight_kg else None,
                "fee_amount": float(obl.fee_amount) if obl and obl.fee_amount else None,
                "currency": obl.currency if obl else None,
            } if obl else None,
        })
    return result


@router.get("/files")
async def list_my_files(
    current_user: Annotated[User, Depends(get_current_user)],
    folder: str | None = Query(None, description="contracts | reports | invoices | audits"),
):
    """List files in the customer's S3 folder."""
    from uusio.storage.s3 import customer_prefix, list_objects
    prefix = customer_prefix(str(current_user.customer_id), folder or "")
    files = list_objects(prefix)
    result = []
    for f in files:
        from uusio.storage.s3 import presigned_url
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
    folder: str = Query("contracts", description="contracts | reports | invoices | audits"),
):
    """Upload a file to the customer's S3 folder."""
    from uusio.storage.s3 import customer_prefix, upload_bytes
    import re
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename or "upload")
    key = f"{customer_prefix(str(current_user.customer_id), folder)}{safe_name}"
    data = await file.read()
    uri = upload_bytes(data, key, file.content_type or "application/octet-stream")
    return {"s3_uri": uri, "filename": safe_name, "folder": folder, "size": len(data)}
