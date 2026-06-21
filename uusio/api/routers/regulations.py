"""EPR regulation library endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user, get_db
from uusio.models.regulation import RegulationEntry
from uusio.models.user import User

router = APIRouter()


def _require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    from fastapi import status
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def _entry_dict(e: RegulationEntry) -> dict:
    return {
        "id": str(e.id),
        "country_code": e.country_code,
        "category": e.category,
        "title": e.title,
        "summary": e.summary,
        "full_text": e.full_text,
        "effective_date": e.effective_date.isoformat() if e.effective_date else None,
        "source_url": e.source_url,
        "tags": e.tags or [],
        "is_active": e.is_active,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }


class RegulationCreate(BaseModel):
    country_code: str
    category: str
    title: str
    summary: str
    full_text: str | None = None
    effective_date: str | None = None
    source_url: str | None = None
    tags: list[str] = []


class RegulationUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    full_text: str | None = None
    effective_date: str | None = None
    source_url: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


@router.get("")
async def list_regulations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    country_code: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    active_only: bool = Query(True),
):
    q = select(RegulationEntry).order_by(RegulationEntry.country_code, RegulationEntry.category)
    if active_only:
        q = q.where(RegulationEntry.is_active == True)  # noqa: E712
    if country_code:
        q = q.where(RegulationEntry.country_code == country_code.upper())
    if category:
        q = q.where(RegulationEntry.category == category)
    if search:
        term = f"%{search}%"
        q = q.where(
            or_(
                RegulationEntry.title.ilike(term),
                RegulationEntry.summary.ilike(term),
                RegulationEntry.full_text.ilike(term),
            )
        )
    rows = (await db.execute(q)).scalars().all()
    return [_entry_dict(r) for r in rows]


@router.post("", status_code=201)
async def create_regulation(
    body: RegulationCreate,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from datetime import date
    entry = RegulationEntry(
        country_code=body.country_code.upper(),
        category=body.category,
        title=body.title,
        summary=body.summary,
        full_text=body.full_text,
        source_url=body.source_url,
        tags=body.tags,
    )
    if body.effective_date:
        entry.effective_date = date.fromisoformat(body.effective_date)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _entry_dict(entry)


@router.patch("/{entry_id}")
async def update_regulation(
    entry_id: uuid.UUID,
    body: RegulationUpdate,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from datetime import date
    entry = (await db.execute(select(RegulationEntry).where(RegulationEntry.id == entry_id))).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Regulation entry not found")
    for field in ("title", "summary", "full_text", "source_url", "tags", "is_active"):
        val = getattr(body, field)
        if val is not None:
            setattr(entry, field, val)
    if body.effective_date is not None:
        entry.effective_date = date.fromisoformat(body.effective_date) if body.effective_date else None
    await db.commit()
    await db.refresh(entry)
    return _entry_dict(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_regulation(
    entry_id: uuid.UUID,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    entry = (await db.execute(select(RegulationEntry).where(RegulationEntry.id == entry_id))).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Regulation entry not found")
    await db.delete(entry)
    await db.commit()
