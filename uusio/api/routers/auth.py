"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user
from uusio.core.database import get_db
from uusio.core.security import create_access_token, hash_password, verify_password
from uusio.models.user import User

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Bootstrap endpoint — only works when no users exist yet.

    After the first admin is created, all new users must be invited
    by an admin via POST /api/v1/admin/organizations/{id}/invite.
    """
    first_user = (await db.execute(select(User))).scalars().first()
    if first_user is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is disabled. Contact your administrator.",
        )
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name or body.email.split("@")[0],
        is_active=True,
        is_admin=True,
        customer_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "is_admin": user.is_admin,
    }


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(User).where(User.email == form_data.username, User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = "admin" if user.is_admin else "member"
    token = create_access_token(
        subject=str(user.id),
        customer_id=str(user.customer_id) if user.customer_id else "",
        email=user.email,
        is_admin=user.is_admin,
    )
    return Token(access_token=token, token_type="bearer", role=role)


@router.get("/me")
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "customer_id": str(current_user.customer_id) if current_user.customer_id else None,
    }
