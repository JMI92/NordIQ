"""Submission endpoints (stub — implemented in step 9)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_submissions():
    return {"message": "Submissions endpoint — coming in build step 9"}
