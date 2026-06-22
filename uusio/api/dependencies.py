"""FastAPI dependency injection helpers."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from uusio.core.database import get_db
from uusio.core.security import decode_access_token
from uusio.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


def require_customer_scope(customer_id: uuid.UUID):
    async def _check(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.customer_id != customer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return current_user
    return _check


async def get_org_scope(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> uuid.UUID:
    """Return the effective org UUID for the current request.

    Members: always their own customer_id.
    Admins: must supply X-Impersonate-Org header to act on a tenant.
    """
    if current_user.is_admin:
        impersonate = request.headers.get("X-Impersonate-Org")
        if impersonate:
            try:
                return uuid.UUID(impersonate)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid X-Impersonate-Org header")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin must supply X-Impersonate-Org header to access tenant data",
        )
    return current_user.customer_id
