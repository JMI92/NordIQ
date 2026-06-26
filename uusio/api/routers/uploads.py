"""File upload endpoint with Claude-powered data analysis.

Flow:
1. Admin or org user uploads Excel/CSV file
2. File is parsed with pandas into a preview
3. Claude analyses the data structure and extracts EPR-relevant data
4. Products, sales volumes, and packaging components are upserted into DB
5. ImportJob tracks the full processing lifecycle
"""

from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user, get_db
from uusio.core.config import get_settings
from uusio.models.audit import ImportJob
from uusio.models.enums import DataSourceType, ImportJobStatus
from uusio.models.packaging import PackagingComponent
from uusio.models.product import Product, ProductWeight
from uusio.models.user import User
from uusio.models.volumes import MonthlySalesVolume, ProductMaterialComposition

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

async def _analyse_with_claude(df_preview: str, filename: str) -> dict:
    """Ask Claude to interpret the DataFrame and extract EPR-relevant fields."""
    if not settings.anthropic_api_key:
        logger.warning("uploads: ANTHROPIC_API_KEY not set, skipping AI analysis")
        return {"products": [], "volumes": [], "packaging": [], "notes": "AI analysis skipped — no API key"}

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        prompt = f"""You are an EPR (Extended Producer Responsibility) compliance data analyst.
A customer has uploaded a file named "{filename}" containing the following data (first 50 rows):

{df_preview}

Your task: extract EPR-relevant data from this table.

Return a JSON object with these keys:
- "products": list of objects with fields: name (str), sku (str or null), category (str, e.g. "Packaging", "Electronics", "Batteries"), country_code (str, 2-letter ISO, or "EU")
- "volumes": list of objects with fields: product_name (str), year (int), month (int, 1-12), units_sold (float), weight_kg (float or null)
- "packaging": list of objects with fields: product_name (str), material_type (str, e.g. "plastic", "cardboard", "glass", "metal"), weight_per_unit_kg (float), is_recyclable (bool)
- "notes": string explaining what you found and any assumptions made

If a field cannot be determined from the data, use null. Be conservative — only include data you are confident about.
Respond with ONLY the JSON object, no other text."""

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code block if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        logger.error("uploads: Claude analysis failed: %s", exc)
        return {"products": [], "volumes": [], "packaging": [], "notes": f"AI analysis error: {exc}"}


# ---------------------------------------------------------------------------
# DB upsert helpers
# ---------------------------------------------------------------------------

async def _upsert_data(session: AsyncSession, customer_id: uuid.UUID, analysis: dict) -> tuple[int, int]:
    """Insert extracted products/volumes/packaging into DB. Returns (inserted, failed)."""
    inserted = 0
    failed = 0

    # Products
    for p in analysis.get("products") or []:
        try:
            name = (p.get("name") or "").strip()
            if not name:
                continue
            existing = (await session.execute(
                select(Product).where(Product.customer_id == customer_id, Product.name == name)
            )).scalar_one_or_none()
            if existing is None:
                product = Product(
                    customer_id=customer_id,
                    name=name,
                    sku=p.get("sku"),
                    category=p.get("category") or "Packaging",
                    country_of_sale=p.get("country_code") or "EU",
                    is_active=True,
                )
                session.add(product)
                inserted += 1
        except Exception as exc:
            logger.warning("uploads: failed to insert product %s: %s", p, exc)
            failed += 1

    await session.flush()

    # Volumes — need to look up product ids
    for v in analysis.get("volumes") or []:
        try:
            product_name = (v.get("product_name") or "").strip()
            if not product_name:
                continue
            product = (await session.execute(
                select(Product).where(Product.customer_id == customer_id, Product.name == product_name)
            )).scalar_one_or_none()
            if product is None:
                continue
            year = int(v.get("year") or 0)
            month = int(v.get("month") or 0)
            if not (year and month):
                continue
            existing_vol = (await session.execute(
                select(MonthlySalesVolume).where(
                    MonthlySalesVolume.product_id == product.id,
                    MonthlySalesVolume.year == year,
                    MonthlySalesVolume.month == month,
                )
            )).scalar_one_or_none()
            if existing_vol is None:
                vol = MonthlySalesVolume(
                    customer_id=customer_id,
                    product_id=product.id,
                    year=year,
                    month=month,
                    units_sold=float(v.get("units_sold") or 0),
                    total_weight_kg=float(v.get("weight_kg") or 0) if v.get("weight_kg") else None,
                )
                session.add(vol)
                inserted += 1
        except Exception as exc:
            logger.warning("uploads: failed to insert volume %s: %s", v, exc)
            failed += 1

    # Packaging compositions
    for pk in analysis.get("packaging") or []:
        try:
            product_name = (pk.get("product_name") or "").strip()
            if not product_name:
                continue
            product = (await session.execute(
                select(Product).where(Product.customer_id == customer_id, Product.name == product_name)
            )).scalar_one_or_none()
            if product is None:
                continue
            material = (pk.get("material_type") or "").strip().lower()
            if not material:
                continue
            existing_pk = (await session.execute(
                select(ProductMaterialComposition).where(
                    ProductMaterialComposition.product_id == product.id,
                    ProductMaterialComposition.material_type == material,
                )
            )).scalar_one_or_none()
            if existing_pk is None:
                comp = ProductMaterialComposition(
                    product_id=product.id,
                    customer_id=customer_id,
                    material_type=material,
                    weight_per_unit_kg=float(pk.get("weight_per_unit_kg") or 0),
                    is_recyclable=bool(pk.get("is_recyclable", False)),
                )
                session.add(comp)
                inserted += 1
        except Exception as exc:
            logger.warning("uploads: failed to insert packaging %s: %s", pk, exc)
            failed += 1

    await session.commit()
    return inserted, failed


# ---------------------------------------------------------------------------
# Background processing task
# ---------------------------------------------------------------------------

async def _process_upload(
    job_id: uuid.UUID,
    customer_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    session_factory,
) -> None:
    """Background task: analyse file with Claude and upsert into DB."""
    from uusio.core.database import async_session_factory as sf
    factory = session_factory or sf

    async with factory() as session:
        job = (await session.execute(select(ImportJob).where(ImportJob.id == job_id))).scalar_one_or_none()
        if job is None:
            return
        job.status = ImportJobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        # Parse file
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.BytesIO(file_bytes))

        df_preview = df.head(50).to_string(index=False, max_cols=20)
        analysis = await _analyse_with_claude(df_preview, filename)

        async with factory() as session:
            inserted, failed = await _upsert_data(session, customer_id, analysis)
            job = (await session.execute(select(ImportJob).where(ImportJob.id == job_id))).scalar_one_or_none()
            if job:
                job.status = ImportJobStatus.COMPLETED if failed == 0 else ImportJobStatus.PARTIAL
                job.records_processed = inserted
                job.records_failed = failed
                job.error_details = {"notes": analysis.get("notes"), "failed": failed}
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()

        logger.info("uploads: job %s completed — %d inserted, %d failed", job_id, inserted, failed)

    except Exception as exc:
        logger.error("uploads: job %s failed: %s", job_id, exc)
        async with factory() as session:
            job = (await session.execute(select(ImportJob).where(ImportJob.id == job_id))).scalar_one_or_none()
            if job:
                job.status = ImportJobStatus.FAILED
                job.error_details = {"error": str(exc)}
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Upload an Excel or CSV file for Claude-powered EPR data extraction.

    Returns a job ID that can be polled for status.
    Extracted products, volumes, and packaging data are upserted automatically.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    customer_id = current_user.customer_id
    if customer_id is None:
        raise HTTPException(status_code=400, detail="User has no associated organisation")

    job = ImportJob(
        customer_id=customer_id,
        data_source_id=None,
        source_type=DataSourceType.CSV,
        status=ImportJobStatus.PENDING,
        records_processed=0,
        records_failed=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from uusio.core.database import async_session_factory
    background_tasks.add_task(
        _process_upload,
        job.id,
        customer_id,
        file_bytes,
        file.filename,
        async_session_factory,
    )

    return {
        "jobId": str(job.id),
        "status": "pending",
        "message": "File received. Claude is analysing your data in the background.",
    }


@router.get("/upload/{job_id}")
async def get_upload_status(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Poll the status of an upload job."""
    job = (await db.execute(select(ImportJob).where(ImportJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.is_admin and job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "jobId": str(job.id),
        "status": job.status.value if hasattr(job.status, "value") else job.status,
        "recordsProcessed": job.records_processed,
        "recordsFailed": job.records_failed,
        "notes": (job.error_details or {}).get("notes"),
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
    }
