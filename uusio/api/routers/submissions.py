"""PRO submission endpoints — generate reports, submit, download, acknowledge."""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user
from uusio.calculators.base import EPRObligation as CalcObligation, ReportingPeriod
from uusio.core.database import get_db
from uusio.models.enums import (
    MaterialType,
    ObligationStatus,
    ProductCategory,
    SubmissionMethod,
    SubmissionStatus,
)
from uusio.models.obligation import EPRObligation
from uusio.models.submission import PROSubmission
from uusio.models.user import User
from uusio.pro_connectors.nordic.connector import NordicPROConnector
from uusio.pro_connectors.nordic.report_generator import NordicReportGenerator

router = APIRouter()

REPORT_OUTPUT_DIR = os.getenv("REPORT_OUTPUT_DIR", "/tmp/uusio_reports")


class SubmitRequest(BaseModel):
    obligation_id: uuid.UUID
    submission_method: SubmissionMethod


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    obligation_id: uuid.UUID
    pro_id: str
    submission_method: str
    status: str
    report_file_path: str | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    response_payload: dict | None

    class Config:
        from_attributes = True


def _to_response(sub: PROSubmission) -> SubmissionResponse:
    return SubmissionResponse(
        id=sub.id,
        obligation_id=sub.obligation_id,
        pro_id=sub.pro_id,
        submission_method=sub.submission_method,
        status=sub.status,
        report_file_path=sub.report_file_path,
        error_message=sub.error_message,
        retry_count=sub.retry_count,
        created_at=sub.created_at,
        response_payload=sub.response_payload,
    )


async def _get_owned_obligation(obligation_id, customer_id, db):
    result = await db.execute(
        select(EPRObligation).where(
            EPRObligation.id == obligation_id,
            EPRObligation.customer_id == customer_id,
        )
    )
    ob = result.scalar_one_or_none()
    if ob is None:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return ob


def _build_calc_obligation(ob: EPRObligation) -> CalcObligation:
    from decimal import Decimal
    snap = ob.calculation_snapshot or {}
    wbm = {m: Decimal(w) for m, w in snap.get("weight_by_material_kg", {}).items()}
    return CalcObligation(
        country_code=ob.country_code,
        pro_id=ob.pro_id,
        product_category=ProductCategory(ob.product_category),
        reporting_period=ReportingPeriod(
            start=ob.reporting_period_start,
            end=ob.reporting_period_end,
        ),
        total_weight_kg=Decimal(str(ob.total_weight_kg)),
        fee_amount=Decimal(str(ob.fee_amount)),
        currency=ob.currency,
        weight_by_material=wbm,
        calculation_snapshot=snap,
    )


@router.get("", response_model=list[SubmissionResponse])
async def list_submissions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    obligation_id: uuid.UUID | None = Query(default=None),
):
    stmt = select(PROSubmission).where(PROSubmission.customer_id == current_user.customer_id)
    if obligation_id is not None:
        stmt = stmt.where(PROSubmission.obligation_id == obligation_id)
    stmt = stmt.order_by(PROSubmission.created_at.desc())
    result = await db.execute(stmt)
    return [_to_response(s) for s in result.scalars().all()]


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_obligation(
    body: SubmitRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate the report file and record a submission attempt.

    Obligation must be FINALISED. Each call creates a new PROSubmission row
    (idempotent retry pattern). portal stays PENDING; api calls the connector.
    """
    ob = await _get_owned_obligation(body.obligation_id, current_user.customer_id, db)
    if ob.status != ObligationStatus.FINALISED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Obligation must be FINALISED before submitting (current: {ob.status})",
        )

    count_result = await db.execute(
        select(PROSubmission).where(
            PROSubmission.obligation_id == ob.id,
            PROSubmission.customer_id == current_user.customer_id,
        )
    )
    prior_attempts = len(count_result.scalars().all())

    calc_ob = _build_calc_obligation(ob)
    generator = NordicReportGenerator(REPORT_OUTPUT_DIR)
    report_file = generator.generate(calc_ob)

    sub = PROSubmission(
        customer_id=current_user.customer_id,
        obligation_id=ob.id,
        pro_id=ob.pro_id,
        submission_method=body.submission_method,
        status=SubmissionStatus.PENDING,
        report_file_path=report_file.file_path,
        retry_count=prior_attempts,
    )
    db.add(sub)
    await db.flush()

    if body.submission_method == SubmissionMethod.API:
        connector = NordicPROConnector()
        result = connector.submit_report(report_file, calc_ob)
        sub.response_payload = result.response_payload
        if result.success:
            sub.status = SubmissionStatus.SUCCESS
            ob.submitted_at = datetime.now(timezone.utc)
            ob.status = ObligationStatus.SUBMITTED
        else:
            sub.status = SubmissionStatus.FAILED
            sub.error_message = result.error_message

    await db.commit()
    await db.refresh(sub)
    return _to_response(sub)


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(PROSubmission).where(
            PROSubmission.id == submission_id,
            PROSubmission.customer_id == current_user.customer_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _to_response(sub)


@router.get("/{submission_id}/download")
async def download_report(
    submission_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream the generated report CSV file."""
    result = await db.execute(
        select(PROSubmission).where(
            PROSubmission.id == submission_id,
            PROSubmission.customer_id == current_user.customer_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not sub.report_file_path:
        raise HTTPException(status_code=404, detail="No report file for this submission")
    if sub.report_file_path.startswith("s3://"):
        from uusio.storage import s3 as s3_storage
        from fastapi.responses import RedirectResponse
        url = s3_storage.presigned_url(sub.report_file_path)
        return RedirectResponse(url=url)
    import os as _os
    if not _os.path.isfile(sub.report_file_path):
        raise HTTPException(status_code=404, detail="Report file not found on disk")
    filename = _os.path.basename(sub.report_file_path)
    return FileResponse(path=sub.report_file_path, media_type="text/csv", filename=filename)


@router.post("/{submission_id}/acknowledge", response_model=SubmissionResponse)
async def acknowledge_submission(
    submission_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark a PENDING portal submission as ACKNOWLEDGED."""
    result = await db.execute(
        select(PROSubmission).where(
            PROSubmission.id == submission_id,
            PROSubmission.customer_id == current_user.customer_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status not in (SubmissionStatus.PENDING,):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only PENDING submissions can be acknowledged (current: {sub.status})",
        )
    sub.status = SubmissionStatus.ACKNOWLEDGED
    ob_result = await db.execute(
        select(EPRObligation).where(
            EPRObligation.id == sub.obligation_id,
            EPRObligation.customer_id == current_user.customer_id,
        )
    )
    ob = ob_result.scalar_one_or_none()
    if ob and ob.status == ObligationStatus.FINALISED:
        ob.submitted_at = datetime.now(timezone.utc)
        ob.status = ObligationStatus.SUBMITTED
    await db.commit()
    await db.refresh(sub)
    return _to_response(sub)
