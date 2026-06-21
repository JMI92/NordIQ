"""Admin-only endpoints: customer management, user management, platform stats."""

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
from uusio.models.obligation import EPRObligation
from uusio.models.submission import PROSubmission
from uusio.models.user import User

router = APIRouter()


def _require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


AdminUser = Annotated[User, Depends(_require_admin)]


# ---------------------------------------------------------------------------
# Stats
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


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

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
            "country_code": c.country_code,
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
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
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


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/customers/{customer_id}/users")
async def list_users(
    customer_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (await db.execute(
        select(User).where(User.customer_id == customer_id).order_by(User.email)
    )).scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows
    ]


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(16))
    user.hashed_password = hash_password(temp_password)
    await db.commit()
    return {"temporary_password": temp_password, "message": "Password reset. Share this with the user securely."}


class UserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    full_name: str | None = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
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
