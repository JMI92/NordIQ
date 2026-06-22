"""Admin-only endpoints: organization management, pro-contracts, platform stats."""

import secrets
import string
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user, get_db
from uusio.core.database import get_db
from uusio.core.security import hash_password
from uusio.models.customer import Customer
from uusio.models.obligation import EPRObligation, ReportingDeadline
from uusio.models.pro_registry import CustomerPRORegistration, PROOrganisation
from uusio.models.product import Product
from uusio.models.submission import PROSubmission
from uusio.models.user import User

router = APIRouter()


def _require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


AdminUser = Annotated[User, Depends(_require_admin)]


def _org_out(c: Customer, active_contracts: int = 0, products_count: int = 0, last_report_at=None) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "country": c.country_of_incorporation,
        "status": "active" if c.is_active else "inactive",
        "contactEmail": c.contact_email or "",
        "activeContracts": active_contracts,
        "productsCount": products_count,
        "lastReportAt": last_report_at.isoformat() if last_report_at else None,
        "createdAt": c.created_at.isoformat(),
    }


def _contract_out(reg: CustomerPRORegistration, pro: PROOrganisation) -> dict:
    return {
        "id": str(reg.id),
        "orgId": str(reg.customer_id),
        "proName": pro.name,
        "country": pro.country_code,
        "materialCategories": reg.material_categories or [pro.category],
        "registrationNumber": reg.registration_number or "",
        "status": reg.status,
        "validFrom": reg.contract_start.isoformat() if reg.contract_start else None,
        "validTo": reg.contract_end.isoformat() if reg.contract_end else None,
    }


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def admin_overview(admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    total_customers = (await db.execute(select(func.count()).select_from(Customer))).scalar()
    active_customers = (await db.execute(
        select(func.count()).select_from(Customer).where(Customer.is_active == True)  # noqa: E712
    )).scalar()
    total_contracts = (await db.execute(select(func.count()).select_from(CustomerPRORegistration))).scalar()

    return {
        "totalCustomers": total_customers,
        "activeCustomers": active_customers,
        "totalContracts": total_contracts,
        "contractsByCountry": [],
        "upcomingDeadlines": [],
        "recentUploads": [],
        "reportingCoverage": [],
    }


# ---------------------------------------------------------------------------
# Organizations (= Customers)
# ---------------------------------------------------------------------------

@router.get("/organizations")
async def list_organizations(admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    customers = (await db.execute(select(Customer).order_by(Customer.name))).scalars().all()
    result = []
    for c in customers:
        active_contracts = (await db.execute(
            select(func.count()).select_from(CustomerPRORegistration)
            .where(CustomerPRORegistration.customer_id == c.id, CustomerPRORegistration.status == "active")
        )).scalar()
        products_count = (await db.execute(
            select(func.count()).select_from(Product).where(Product.customer_id == c.id)
        )).scalar()
        result.append(_org_out(c, active_contracts, products_count))
    return result


class OrgCreate(BaseModel):
    name: str
    country: str
    contactEmail: str = ""


class OrgUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    contactEmail: str | None = None
    status: str | None = None


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(body: OrgCreate, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    customer = Customer(
        name=body.name,
        country_of_incorporation=body.country,
        contact_email=body.contactEmail or None,
        is_active=True,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return _org_out(customer)


@router.patch("/organizations/{org_id}")
async def update_organization(
    org_id: uuid.UUID, body: OrgUpdate, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    c = (await db.execute(select(Customer).where(Customer.id == org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Organization not found")
    if body.name is not None:
        c.name = body.name
    if body.country is not None:
        c.country_of_incorporation = body.country
    if body.contactEmail is not None:
        c.contact_email = body.contactEmail
    if body.status is not None:
        c.is_active = body.status == "active"
    await db.commit()
    await db.refresh(c)
    return _org_out(c)


@router.post("/organizations/{org_id}/invite")
async def invite_user(
    org_id: uuid.UUID,
    body: dict,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    c = (await db.execute(select(Customer).where(Customer.id == org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Organization not found")
    email = body.get("email", "")
    if not email:
        raise HTTPException(status_code=400, detail="email required")
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")
    temp_password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    user = User(
        customer_id=org_id,
        email=email,
        hashed_password=hash_password(temp_password),
        full_name=email.split("@")[0],
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    await db.commit()
    return {"ok": True, "temporaryPassword": temp_password}


# ---------------------------------------------------------------------------
# PRO Contracts
# ---------------------------------------------------------------------------

@router.get("/organizations/{org_id}/pro-contracts")
async def list_pro_contracts(
    org_id: uuid.UUID, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    rows = (await db.execute(
        select(CustomerPRORegistration, PROOrganisation)
        .join(PROOrganisation, CustomerPRORegistration.pro_id == PROOrganisation.id)
        .where(CustomerPRORegistration.customer_id == org_id)
    )).all()
    return [_contract_out(reg, pro) for reg, pro in rows]


class ProContractCreate(BaseModel):
    proName: str
    country: str
    materialCategories: list[str] = []
    registrationNumber: str = ""
    status: str = "active"
    validFrom: str | None = None
    validTo: str | None = None


class ProContractUpdate(BaseModel):
    materialCategories: list[str] | None = None
    registrationNumber: str | None = None
    status: str | None = None
    validFrom: str | None = None
    validTo: str | None = None


@router.post("/organizations/{org_id}/pro-contracts", status_code=status.HTTP_201_CREATED)
async def create_pro_contract(
    org_id: uuid.UUID,
    body: ProContractCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    c = (await db.execute(select(Customer).where(Customer.id == org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Organization not found")

    category = body.materialCategories[0] if body.materialCategories else "packaging"
    pro_key = f"{body.proName.lower().replace(' ', '-')}-{body.country.lower()}-{uuid.uuid4().hex[:6]}"
    pro = PROOrganisation(
        name=body.proName,
        country_code=body.country,
        category=category,
        pro_key=pro_key,
        is_active=True,
    )
    db.add(pro)
    await db.flush()

    from datetime import date
    reg = CustomerPRORegistration(
        customer_id=org_id,
        pro_id=pro.id,
        registration_number=body.registrationNumber or None,
        material_categories=body.materialCategories,
        status=body.status,
        contract_start=date.fromisoformat(body.validFrom) if body.validFrom else None,
        contract_end=date.fromisoformat(body.validTo) if body.validTo else None,
    )
    db.add(reg)
    await db.commit()
    await db.refresh(reg)
    return _contract_out(reg, pro)


@router.patch("/pro-contracts/{contract_id}")
async def update_pro_contract(
    contract_id: uuid.UUID,
    body: ProContractUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(
        select(CustomerPRORegistration, PROOrganisation)
        .join(PROOrganisation, CustomerPRORegistration.pro_id == PROOrganisation.id)
        .where(CustomerPRORegistration.id == contract_id)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    reg, pro = row
    from datetime import date
    if body.materialCategories is not None:
        reg.material_categories = body.materialCategories
    if body.registrationNumber is not None:
        reg.registration_number = body.registrationNumber
    if body.status is not None:
        reg.status = body.status
    if body.validFrom is not None:
        reg.contract_start = date.fromisoformat(body.validFrom)
    if body.validTo is not None:
        reg.contract_end = date.fromisoformat(body.validTo)
    await db.commit()
    await db.refresh(reg)
    return _contract_out(reg, pro)


@router.delete("/pro-contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pro_contract(
    contract_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    reg = (await db.execute(
        select(CustomerPRORegistration).where(CustomerPRORegistration.id == contract_id)
    )).scalar_one_or_none()
    if not reg:
        raise HTTPException(status_code=404, detail="Contract not found")
    await db.delete(reg)
    await db.commit()


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backwards compat)
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_stats(admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    total_customers = (await db.execute(select(func.count()).select_from(Customer))).scalar()
    active_customers = (await db.execute(
        select(func.count()).select_from(Customer).where(Customer.is_active == True)  # noqa: E712
    )).scalar()
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar()
    total_obligations = (await db.execute(select(func.count()).select_from(EPRObligation))).scalar()
    total_submissions = (await db.execute(select(func.count()).select_from(PROSubmission))).scalar()
    return {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "total_users": total_users,
        "total_obligations": total_obligations,
        "total_submissions": total_submissions,
    }


@router.get("/customers")
async def list_customers(admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(Customer).order_by(Customer.name))).scalars().all()
    result = []
    for c in rows:
        user_count = (await db.execute(
            select(func.count()).select_from(User).where(User.customer_id == c.id)
        )).scalar()
        result.append({
            "id": str(c.id),
            "name": c.name,
            "vat_number": c.vat_number,
            "country_code": c.country_of_incorporation,
            "is_active": c.is_active,
            "user_count": user_count,
            "created_at": c.created_at.isoformat(),
        })
    return result


class CustomerUpdate(BaseModel):
    is_active: bool | None = None
    name: str | None = None


@router.patch("/customers/{customer_id}")
async def update_customer(
    customer_id: uuid.UUID, body: CustomerUpdate, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if body.is_active is not None:
        customer.is_active = body.is_active
    if body.name is not None:
        customer.name = body.name
    await db.commit()
    await db.refresh(customer)
    return {"id": str(customer.id), "name": customer.name, "is_active": customer.is_active}


@router.get("/customers/{customer_id}/users")
async def list_users(
    customer_id: uuid.UUID, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    rows = (await db.execute(
        select(User).where(User.customer_id == customer_id).order_by(User.email)
    )).scalars().all()
    return [
        {"id": str(u.id), "email": u.email, "full_name": u.full_name,
         "is_active": u.is_active, "is_admin": u.is_admin, "created_at": u.created_at.isoformat()}
        for u in rows
    ]


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: uuid.UUID, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    temp_password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    user.hashed_password = hash_password(temp_password)
    await db.commit()
    return {"temporary_password": temp_password}


class UserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    full_name: str | None = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, db: Annotated[AsyncSession, Depends(get_db)]
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.full_name is not None:
        user.full_name = body.full_name
    await db.commit()
    return {"id": str(user.id), "email": user.email, "is_active": user.is_active, "is_admin": user.is_admin}
