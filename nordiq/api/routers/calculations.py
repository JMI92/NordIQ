"""EPR calculation endpoints (stub — implemented in step 5)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_calculations():
    return {"message": "Calculations endpoint — coming in build step 5"}
