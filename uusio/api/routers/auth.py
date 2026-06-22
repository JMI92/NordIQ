"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user
from uusio.core.database import get_db
from uusio.core.security import create_access_token, hash_password, verify_password
from uusio.models.customer import Customer
from uusio.models.user import User

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str
    country_code: str = "FI"


class RegisterResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_admin: bool
    active: bool
    message: str


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
    token = create_access_token(subject=str(user.id), customer_id=str(user.customer_id))
    return Token(access_token=token, token_type="bearer")


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Self-registration endpoint.

    The very first registered user becomes admin and is activated immediately.
    Subsequent users are created inactive and must be activated by an admin.
    """
    # Check email not already taken
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered.")

    # Is this the first user ever?
    user_count_result = await db.execute(select(func.count()).select_from(User))
    is_first_user = (user_count_result.scalar_one() == 0)

    # Create a customer (tenant) for this registration
    customer = Customer(
        name=body.company_name,
        country_of_incorporation=body.country_code.upper()[:2],
        is_active=True,
    )
    db.add(customer)
    await db.flush()  # get customer.id

    user = User(
        customer_id=customer.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        is_active=is_first_user,   # first user active immediately
        is_admin=is_first_user,    # first user is admin
    )
    db.add(user)
    await db.flush()

    if is_first_user:
        msg = "Account created. You can log in now."
    else:
        msg = "Account created. An admin must activate it before you can log in."

    return RegisterResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_admin=user.is_admin,
        active=user.is_active,
        message=msg,
    )


@router.get("/me")
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "customer_id": str(current_user.customer_id),
    }
