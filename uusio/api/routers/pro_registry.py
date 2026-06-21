"""PRO organisation registry — admin CRUD + customer registration management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user, get_db
from uusio.models.pro_registry import CustomerPRORegistration, PROOrganisation
from uusio.models.user import User

router = APIRouter()


def _require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    from fastapi import status
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def _pro_dict(p: PROOrganisation) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "country_code": p.country_code,
        "category": p.category,
        "pro_key": p.pro_key,
        "website": p.website,
        "portal_url": p.portal_url,
        "api_endpoint": p.api_endpoint,
        "contact_name": p.contact_name,
        "contact_email": p.contact_email,
        "contact_phone": p.contact_phone,
        "reporting_deadline_notes": p.reporting_deadline_notes,
        "notes": p.notes,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
    }


def _reg_dict(r: CustomerPRORegistration) -> dict:
    d = {
        "id": str(r.id),
        "customer_id": str(r.customer_id),
        "pro_id": str(r.pro_id),
        "registration_number": r.registration_number,
        "status": r.status,
        "contract_start": r.contract_start.isoformat() if r.contract_start else None,
        "contract_end": r.contract_end.isoformat() if r.contract_end else None,
        "notes": r.notes,
        "created_at": r.created_at.isoformat(),
    }
    if r.pro is not None:
        d["pro"] = _pro_dict(r.pro)
    return d


# -------------------------------------------------------------------------
# PRO organisations (admin only)
# -------------------------------------------------------------------------

class PROCreate(BaseModel):
    name: str
    country_code: str
    category: str
    pro_key: str
    website: str | None = None
    portal_url: str | None = None
    api_endpoint: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    reporting_deadline_notes: str | None = None
    notes: str | None = None


class PROUpdate(BaseModel):
    name: str | None = None
    website: str | None = None
    portal_url: str | None = None
    api_endpoint: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    reporting_deadline_notes: str | None = None
    notes: str | None = None
    is_active: bool | None = None


@router.get("/pros")
async def list_pros(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    country_code: str | None = Query(None),
    category: str | None = Query(None),
    active_only: bool = Query(True),
):
    q = select(PROOrganisation).order_by(PROOrganisation.country_code, PROOrganisation.name)
    if active_only:
        q = q.where(PROOrganisation.is_active == True)  # noqa: E712
    if country_code:
        q = q.where(PROOrganisation.country_code == country_code.upper())
    if category:
        q = q.where(PROOrganisation.category == category)
    rows = (await db.execute(q)).scalars().all()
    return [_pro_dict(p) for p in rows]


@router.post("/pros", status_code=201)
async def create_pro(
    body: PROCreate,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    pro = PROOrganisation(**body.model_dump())
    pro.country_code = pro.country_code.upper()
    db.add(pro)
    await db.commit()
    await db.refresh(pro)
    return _pro_dict(pro)


@router.patch("/pros/{pro_id}")
async def update_pro(
    pro_id: uuid.UUID,
    body: PROUpdate,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    pro = (await db.execute(select(PROOrganisation).where(PROOrganisation.id == pro_id))).scalar_one_or_none()
    if not pro:
        raise HTTPException(status_code=404, detail="PRO not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(pro, field, value)
    await db.commit()
    await db.refresh(pro)
    return _pro_dict(pro)


@router.delete("/pros/{pro_id}", status_code=204)
async def delete_pro(
    pro_id: uuid.UUID,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    pro = (await db.execute(select(PROOrganisation).where(PROOrganisation.id == pro_id))).scalar_one_or_none()
    if not pro:
        raise HTTPException(status_code=404, detail="PRO not found")
    await db.delete(pro)
    await db.commit()


# -------------------------------------------------------------------------
# Customer PRO registrations
# -------------------------------------------------------------------------

class RegistrationCreate(BaseModel):
    customer_id: uuid.UUID
    pro_id: uuid.UUID
    registration_number: str | None = None
    status: str = "active"
    contract_start: str | None = None
    contract_end: str | None = None
    notes: str | None = None


class RegistrationUpdate(BaseModel):
    registration_number: str | None = None
    status: str | None = None
    contract_start: str | None = None
    contract_end: str | None = None
    notes: str | None = None


@router.get("/registrations")
async def list_registrations(
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    customer_id: uuid.UUID | None = Query(None),
):
    from sqlalchemy.orm import selectinload
    q = select(CustomerPRORegistration).options(selectinload(CustomerPRORegistration.pro))
    if customer_id:
        q = q.where(CustomerPRORegistration.customer_id == customer_id)
    rows = (await db.execute(q)).scalars().all()
    return [_reg_dict(r) for r in rows]


@router.post("/registrations", status_code=201)
async def create_registration(
    body: RegistrationCreate,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from datetime import date
    from sqlalchemy.orm import selectinload
    reg = CustomerPRORegistration(
        customer_id=body.customer_id,
        pro_id=body.pro_id,
        registration_number=body.registration_number,
        status=body.status,
        notes=body.notes,
    )
    if body.contract_start:
        reg.contract_start = date.fromisoformat(body.contract_start)
    if body.contract_end:
        reg.contract_end = date.fromisoformat(body.contract_end)
    db.add(reg)
    await db.commit()
    result = await db.execute(
        select(CustomerPRORegistration)
        .options(selectinload(CustomerPRORegistration.pro))
        .where(CustomerPRORegistration.id == reg.id)
    )
    return _reg_dict(result.scalar_one())


@router.patch("/registrations/{reg_id}")
async def update_registration(
    reg_id: uuid.UUID,
    body: RegistrationUpdate,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from datetime import date
    from sqlalchemy.orm import selectinload
    reg = (await db.execute(
        select(CustomerPRORegistration)
        .options(selectinload(CustomerPRORegistration.pro))
        .where(CustomerPRORegistration.id == reg_id)
    )).scalar_one_or_none()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")
    if body.registration_number is not None:
        reg.registration_number = body.registration_number
    if body.status is not None:
        reg.status = body.status
    if body.notes is not None:
        reg.notes = body.notes
    if body.contract_start is not None:
        reg.contract_start = date.fromisoformat(body.contract_start)
    if body.contract_end is not None:
        reg.contract_end = date.fromisoformat(body.contract_end)
    await db.commit()
    await db.refresh(reg)
    return _reg_dict(reg)


@router.delete("/registrations/{reg_id}", status_code=204)
async def delete_registration(
    reg_id: uuid.UUID,
    admin: Annotated[User, Depends(_require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    reg = (await db.execute(
        select(CustomerPRORegistration).where(CustomerPRORegistration.id == reg_id)
    )).scalar_one_or_none()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")
    await db.delete(reg)
    await db.commit()
