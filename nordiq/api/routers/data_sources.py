"""Data source management endpoints (stub — implemented in step 3/4)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_data_sources():
    return {"message": "Data sources endpoint — coming in build step 3"}
