"""NordIQ FastAPI application entry point."""

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
    title="NordIQ EPR Compliance API",
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

from nordiq.api.routers import auth, customers, data_sources, products, calculations, submissions, audit  # noqa: E402

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(customers.router, prefix="/api/v1/customers", tags=["customers"])
app.include_router(data_sources.router, prefix="/api/v1/data-sources", tags=["data-sources"])
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])
app.include_router(calculations.router, prefix="/api/v1/calculations", tags=["calculations"])
app.include_router(submissions.router, prefix="/api/v1/submissions", tags=["submissions"])
app.include_router(audit.router, prefix="/api/v1/audit-log", tags=["audit"])


@app.get("/health", tags=["health"])
async def health_check():
    """Liveness probe — returns 200 if the API is running and DB is reachable."""
    db_ok = await check_db_connection()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
