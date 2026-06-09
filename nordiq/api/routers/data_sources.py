"""Data source management endpoints — list, create, update, delete, test connection."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nordiq.api.dependencies import get_current_user
from nordiq.core.database import get_db
from nordiq.core.security import decrypt_config, encrypt_config
from nordiq.ingestion.csv_ingestor import CSVIngestor
from nordiq.ingestion.base import DataSourceConfig
from nordiq.models.customer import CustomerDataSource
from nordiq.models.enums import DataSourceType
from nordiq.models.user import User

router = APIRouter()


class DataSourceCreate(BaseModel):
    name: str
    source_type: DataSourceType
    connection_config: dict  # plaintext — encrypted before DB write
    table_name: str | None = None
    field_mapping: dict | None = None


class DataSourceUpdate(BaseModel):
    name: str | None = None
    connection_config: dict | None = None
    table_name: str | None = None
    field_mapping: dict | None = None
    is_active: bool | None = None


class DataSourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    table_name: str | None
    field_mapping: dict | None
    is_active: bool
    last_synced_at: str | None

    class Config:
        from_attributes = True


def _to_response(ds: CustomerDataSource) -> DataSourceResponse:
    return DataSourceResponse(
        id=ds.id,
        name=ds.name,
        source_type=ds.source_type,
        table_name=ds.table_name,
        field_mapping=ds.field_mapping,
        is_active=ds.is_active,
        last_synced_at=ds.last_synced_at.isoformat() if ds.last_synced_at else None,
    )


@router.get("")
async def list_data_sources(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DataSourceResponse]:
    result = await db.execute(
        select(CustomerDataSource).where(
            CustomerDataSource.customer_id == current_user.customer_id
        )
    )
    return [_to_response(ds) for ds in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_data_source(
    body: DataSourceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataSourceResponse:
    encrypted = encrypt_config(body.connection_config)
    ds = CustomerDataSource(
        customer_id=current_user.customer_id,
        name=body.name,
        source_type=body.source_type,
        connection_config=encrypted,
        table_name=body.table_name,
        field_mapping=body.field_mapping,
    )
    db.add(ds)
    await db.flush()
    return _to_response(ds)


@router.get("/{ds_id}")
async def get_data_source(
    ds_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataSourceResponse:
    ds = await _get_owned(ds_id, current_user, db)
    return _to_response(ds)


@router.patch("/{ds_id}")
async def update_data_source(
    ds_id: uuid.UUID,
    body: DataSourceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataSourceResponse:
    ds = await _get_owned(ds_id, current_user, db)
    if body.name is not None:
        ds.name = body.name
    if body.connection_config is not None:
        ds.connection_config = encrypt_config(body.connection_config)
    if body.table_name is not None:
        ds.table_name = body.table_name
    if body.field_mapping is not None:
        ds.field_mapping = body.field_mapping
    if body.is_active is not None:
        ds.is_active = body.is_active
    await db.flush()
    return _to_response(ds)


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    ds_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    ds = await _get_owned(ds_id, current_user, db)
    await db.delete(ds)


@router.post("/{ds_id}/test")
async def test_data_source_connection(
    ds_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Test that the data source is reachable and the field mapping is valid."""
    ds = await _get_owned(ds_id, current_user, db)
    if ds.connection_config is None:
        return {"ok": False, "detail": "No connection config stored."}

    conn = decrypt_config(ds.connection_config)
    cfg = DataSourceConfig(
        source_type=ds.source_type,
        connection_config=conn,
        field_mapping=ds.field_mapping or {},
        table_name=ds.table_name,
    )

    if ds.source_type == DataSourceType.CSV:
        ok = CSVIngestor().validate_connection(cfg)
    elif ds.source_type == DataSourceType.SNOWFLAKE:
        try:
            from nordiq.ingestion.snowflake_ingestor import SnowflakeIngestor
            ok = SnowflakeIngestor().validate_connection(cfg)
        except ImportError:
            return {"ok": False, "detail": "snowflake-connector-python is not installed."}
    else:
        return {"ok": False, "detail": f"Test not implemented for source type '{ds.source_type}'."}

    return {"ok": ok, "detail": "Connection successful." if ok else "Connection failed."}


async def _get_owned(
    ds_id: uuid.UUID, user: User, db: AsyncSession
) -> CustomerDataSource:
    result = await db.execute(
        select(CustomerDataSource).where(
            CustomerDataSource.id == ds_id,
            CustomerDataSource.customer_id == user.customer_id,
        )
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found.")
    return ds
