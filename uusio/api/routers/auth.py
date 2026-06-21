"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.api.dependencies import get_current_user
from uusio.core.database import get_db
from uusio.core.security import create_access_token, verify_password
from uusio.models.user import User

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str


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
