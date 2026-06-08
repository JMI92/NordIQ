"""Product endpoints (stub — implemented in step 7)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_products():
    return {"message": "Products endpoint — coming in build step 7"}
