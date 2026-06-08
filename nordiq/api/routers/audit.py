"""Audit log endpoints (stub — implemented later)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_audit_log():
    return {"message": "Audit log endpoint — coming soon"}
