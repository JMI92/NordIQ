"""Admin-only endpoints: organization management, pro-contracts, platform stats."""

import logging
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
from uusio.services.google_drive import create_customer_folder

logger = logging.getLogger(__name__)

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
        "submissionMethod": pro.submission_method,
        "submissionEmail": pro.submission_email,
        "submissionApiUrl": pro.submission_api_url,
        "submissionNotes": pro.submission_notes,
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

    # Create Google Drive folder for the customer (non-blocking — failure doesn't abort)
    try:
        folder_id = await create_customer_folder(customer.name)
        if folder_id:
            customer.drive_folder_id = folder_id
            await db.commit()
            logger.info("Drive folder created for customer %s: %s", customer.id, folder_id)
        else:
            logger.warning("Drive folder not created for customer %s (Drive not configured?)", customer.id)
    except Exception:
        logger.exception("Unexpected error creating Drive folder for customer %s", customer.id)

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
# PRO Submission configuration
# ---------------------------------------------------------------------------

class ProSubmissionConfig(BaseModel):
    submissionMethod: str | None = None   # email | api | portal | manual
    submissionEmail: str | None = None
    submissionApiUrl: str | None = None
    submissionApiKey: str | None = None   # plaintext; stored encrypted
    submissionNotes: str | None = None


@router.patch("/pro-contracts/{contract_id}/submission-config")
async def update_pro_submission_config(
    contract_id: uuid.UUID,
    body: ProSubmissionConfig,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Configure how reports are submitted to a specific PRO.

    Called when onboarding a new PRO to define whether submissions happen
    via email, API, portal upload, or manual process.
    """
    row = (await db.execute(
        select(CustomerPRORegistration, PROOrganisation)
        .join(PROOrganisation, CustomerPRORegistration.pro_id == PROOrganisation.id)
        .where(CustomerPRORegistration.id == contract_id)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    reg, pro = row

    if body.submissionMethod is not None:
        pro.submission_method = body.submissionMethod
    if body.submissionEmail is not None:
        pro.submission_email = body.submissionEmail
    if body.submissionApiUrl is not None:
        pro.submission_api_url = body.submissionApiUrl
    if body.submissionApiKey is not None:
        from uusio.core.security import encrypt_config
        pro.submission_api_key_encrypted = encrypt_config({"key": body.submissionApiKey})
    if body.submissionNotes is not None:
        pro.submission_notes = body.submissionNotes

    await db.commit()
    await db.refresh(pro)
    return _contract_out(reg, pro)


# ---------------------------------------------------------------------------
# Onboarding: create customer + first user in one call
# ---------------------------------------------------------------------------

class OnboardCustomerBody(BaseModel):
    # Customer fields
    company_name: str
    country_of_incorporation: str          # 2-letter ISO, e.g. "FI"
    vat_number: str | None = None
    contact_email: str | None = None
    # First user
    user_email: str
    user_full_name: str | None = None
    user_is_admin: bool = False


@router.post("/onboard-customer", status_code=status.HTTP_201_CREATED)
async def onboard_customer(
    body: OnboardCustomerBody,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new customer and their first user account in one call.

    Returns the customer record plus a temporary password for the user.
    Send the temporary password to the user out-of-band — it is shown only once.
    """
    existing = (await db.execute(select(User).where(User.email == body.user_email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="A user with that email already exists")

    customer = Customer(
        name=body.company_name,
        country_of_incorporation=body.country_of_incorporation.upper(),
        vat_number=body.vat_number or None,
        contact_email=body.contact_email or None,
        is_active=True,
    )
    db.add(customer)
    await db.flush()

    temp_password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    user = User(
        customer_id=customer.id,
        email=body.user_email,
        hashed_password=hash_password(temp_password),
        full_name=body.user_full_name or body.user_email.split("@")[0],
        is_active=True,
        is_admin=body.user_is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(customer)
    await db.refresh(user)

    return {
        "customer": _org_out(customer),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_admin": user.is_admin,
        },
        "temporary_password": temp_password,
        "onboarding_status_url": f"/api/v1/admin/customers/{customer.id}/onboarding-status",
    }


# ---------------------------------------------------------------------------
# Onboarding status — shows what's complete and what's missing per customer
# ---------------------------------------------------------------------------

@router.get("/customers/{customer_id}/onboarding-status")
async def get_onboarding_status(
    customer_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return a checklist of onboarding steps for a customer.

    Each step has: done (bool), count (int where relevant), detail (str).
    Use this to quickly see what's missing before a customer goes live.
    """
    from uusio.models.billing import Invoice
    from uusio.models.packaging import PackagingComponent

    c = (await db.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")

    users = (await db.execute(
        select(func.count()).select_from(User).where(User.customer_id == customer_id)
    )).scalar() or 0

    products = (await db.execute(
        select(func.count()).select_from(Product).where(Product.customer_id == customer_id)
    )).scalar() or 0

    pro_regs = (await db.execute(
        select(func.count()).select_from(CustomerPRORegistration)
        .where(CustomerPRORegistration.customer_id == customer_id, CustomerPRORegistration.status == "active")
    )).scalar() or 0

    obligations = (await db.execute(
        select(func.count()).select_from(EPRObligation)
        .where(EPRObligation.customer_id == customer_id)
    )).scalar() or 0

    calculated = (await db.execute(
        select(func.count()).select_from(EPRObligation)
        .where(EPRObligation.customer_id == customer_id, EPRObligation.status == "calculated")
    )).scalar() or 0

    submitted = (await db.execute(
        select(func.count()).select_from(EPRObligation)
        .where(EPRObligation.customer_id == customer_id, EPRObligation.status == "submitted")
    )).scalar() or 0

    invoices = (await db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.customer_id == customer_id)
    )).scalar() or 0

    packaging = (await db.execute(
        select(func.count()).select_from(PackagingComponent)
        .where(PackagingComponent.customer_id == customer_id)
    )).scalar() or 0

    steps = [
        {
            "step": "customer_created",
            "label": "Customer account created",
            "done": True,
            "detail": c.name,
        },
        {
            "step": "user_created",
            "label": "First user account created",
            "done": users > 0,
            "count": users,
            "detail": f"{users} user(s)" if users else "No users yet — use /admin/onboard-customer or /admin/organizations/{customer_id}/invite",
        },
        {
            "step": "pro_registrations",
            "label": "PRO registrations configured",
            "done": pro_regs > 0,
            "count": pro_regs,
            "detail": f"{pro_regs} active registration(s)" if pro_regs else "No PRO registrations — add via /admin/organizations/{customer_id}/pro-contracts",
        },
        {
            "step": "products_entered",
            "label": "Products entered",
            "done": products > 0,
            "count": products,
            "detail": f"{products} product(s)" if products else "No products — customer must enter products via the portal",
        },
        {
            "step": "packaging_components",
            "label": "Packaging components defined",
            "done": packaging > 0,
            "count": packaging,
            "detail": f"{packaging} packaging component(s)" if packaging else "No packaging components defined",
        },
        {
            "step": "obligations_created",
            "label": "EPR obligations created",
            "done": obligations > 0,
            "count": obligations,
            "detail": f"{obligations} obligation(s) total, {calculated} calculated, {submitted} submitted",
        },
        {
            "step": "first_calculation",
            "label": "First EPR calculation run",
            "done": calculated > 0 or submitted > 0,
            "detail": f"{calculated} calculated, {submitted} submitted" if (calculated or submitted) else "No calculations yet — trigger via /api/v1/calculations",
        },
        {
            "step": "invoicing",
            "label": "Invoicing active",
            "done": invoices > 0,
            "count": invoices,
            "detail": f"{invoices} invoice(s) generated" if invoices else "No invoices yet — runs automatically on 1st of month",
        },
    ]

    completed = sum(1 for s in steps if s["done"])
    return {
        "customer_id": str(customer_id),
        "customer_name": c.name,
        "is_active": c.is_active,
        "completed_steps": completed,
        "total_steps": len(steps),
        "ready_for_live": completed == len(steps),
        "steps": steps,
    }


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
