# api/routers/auth.py — Authentication endpoints (placeholder)
# Google OAuth will be wired up in Session 3.

from fastapi import APIRouter

router = APIRouter()


@router.get("")
def auth_status():
    return {"status": "auth coming soon"}
