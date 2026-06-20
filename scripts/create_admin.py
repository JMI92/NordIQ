#!/usr/bin/env python3
"""One-off script: create initial admin user and customer tenant.

Usage (inside container):
    python scripts/create_admin.py
"""
import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")

from nordiq.core.security import hash_password
from nordiq.models.customer import Customer
from nordiq.models.user import User
import nordiq.models  # noqa: F401 — ensure all models are registered

EMAIL = os.environ.get("ADMIN_EMAIL", "juho@uusio.io")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
FULL_NAME = os.environ.get("ADMIN_FULL_NAME", "Juho Ikäläinen")
CUSTOMER_NAME = os.environ.get("CUSTOMER_NAME", "Uusio")


async def main() -> None:
    if not PASSWORD:
        print("ERROR: set ADMIN_PASSWORD env var", file=sys.stderr)
        sys.exit(1)

    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == EMAIL))
        if result.scalar_one_or_none():
            print(f"User {EMAIL} already exists — nothing to do.")
            return

        # Create customer tenant
        customer = Customer(
            name=CUSTOMER_NAME,
            country_of_incorporation="FI",
        )
        session.add(customer)
        await session.flush()

        # Create admin user
        user = User(
            customer_id=customer.id,
            email=EMAIL,
            hashed_password=hash_password(PASSWORD),
            full_name=FULL_NAME,
            is_active=True,
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        print(f"Created customer '{CUSTOMER_NAME}' (id={customer.id})")
        print(f"Created admin user '{EMAIL}' (id={user.id})")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
