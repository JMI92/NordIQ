"""UUSIO FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nordiq.core.config import get_settings
from nordiq.core.database import check_db_connection

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ok = await check_db_connection()
    if not ok:
        raise RuntimeError("Database connection failed on startup")

    from nordiq.core.database import async_session_factory
    from nordiq.scheduler.jobs import setup_scheduler, shutdown_scheduler
    setup_scheduler(async_session_factory)

    yield

    from nordiq.scheduler.jobs import shutdown_scheduler  # noqa: F811
    shutdown_scheduler()


app = FastAPI(
    title="UUSIO EPR Compliance API",
    description="API for managing EPR (Extended Producer Responsibility) compliance obligations.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from nordiq.api.routers import auth, customers, data_sources, products, calculations, submissions, audit, packaging  # noqa: E402

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(customers.router, prefix="/api/v1/customers", tags=["customers"])
app.include_router(data_sources.router, prefix="/api/v1/data-sources", tags=["data-sources"])
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])
app.include_router(calculations.router, prefix="/api/v1/calculations", tags=["calculations"])
app.include_router(submissions.router, prefix="/api/v1/submissions", tags=["submissions"])
app.include_router(audit.router, prefix="/api/v1/audit-log", tags=["audit"])
app.include_router(packaging.router, prefix="/api/v1/packaging-components", tags=["Packaging"])


@app.get("/health", tags=["health"])
async def health_check():
    """Liveness probe — returns 200 if the API is running and DB is reachable."""
    db_ok = await check_db_connection()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}


@app.post("/api/v1/admin/seed", tags=["admin"], include_in_schema=False)
async def seed_admin(token: str):
    """One-time admin user creation. Disabled once an admin exists."""
    import os
    if token != os.environ.get("SEED_TOKEN", ""):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    from sqlalchemy import select
    from nordiq.core.database import async_session_factory
    from nordiq.core.security import hash_password
    from nordiq.models.customer import Customer
    from nordiq.models.user import User

    async with async_session_factory() as db:
        existing = await db.execute(select(User).where(User.is_admin == True))  # noqa: E712
        if existing.scalar_one_or_none():
            return {"status": "already_exists"}

        customer = Customer(name="Uusio", country_of_incorporation="FI")
        db.add(customer)
        await db.flush()

        user = User(
            customer_id=customer.id,
            email="juho@uusio.io",
            hashed_password=hash_password("Juhoika2203!"),
            full_name="Juho Ikäläinen",
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        await db.commit()
        return {"status": "created", "email": user.email, "customer_id": str(customer.id)}
