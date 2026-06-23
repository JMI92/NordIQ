"""Alembic environment configuration with async support."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Import the base and all models so Alembic can detect them
from uusio.core.database import Base
import uusio.models  # noqa: F401 — registers all models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Prefer DATABASE_URL env var over alembic.ini value."""
    import os
    return os.environ.get("SYNC_DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = get_url()
    # Use sync driver for Alembic migrations
    sync_url = url.replace("+asyncpg", "").replace("+aiosqlite", "")
    connectable = create_async_engine(
        url if "+asyncpg" in url or "+aiosqlite" in url else f"postgresql+asyncpg{url[len('postgresql'):]}"
    )
    # Fall back to sync engine for Alembic
    from sqlalchemy import create_engine
    sync_engine = create_engine(sync_url)
    with sync_engine.connect() as connection:
        do_run_migrations(connection)
    sync_engine.dispose()


def run_migrations_online() -> None:
    url = get_url()
    # Strip async driver prefix for Alembic — it requires a sync connection
    sync_url = url.replace("+asyncpg", "").replace("+aiosqlite", "")
    from sqlalchemy import create_engine
    connectable = create_engine(
        sync_url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
