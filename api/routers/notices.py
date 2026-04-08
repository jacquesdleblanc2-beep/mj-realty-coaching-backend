# api/routers/notices.py — Notices endpoints
#
# GET    /api/notices              — active notices (filtered by ?audience=)
# GET    /api/notices/all          — all notices including inactive (admin)
# POST   /api/notices              — create notice
# PUT    /api/notices/{id}         — update notice
# DELETE /api/notices/{id}         — soft delete (active=false)
# PATCH  /api/notices/read         — mark notice read/unread for a user

import os
import sys
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import crud

router = APIRouter()


# ── Models ─────────────────────────────────────────────────────────────────────

class NoticeCreate(BaseModel):
    title:    str
    body:     str
    audience: str = "all"


class NoticeUpdate(BaseModel):
    title:    Optional[str]  = None
    body:     Optional[str]  = None
    audience: Optional[str]  = None
    active:   Optional[bool] = None


class ReadPatch(BaseModel):
    user_id:   str
    user_type: str   # "realtor" or "coach"
    notice_id: str
    read:      bool


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def list_notices(audience: Optional[str] = None):
    return crud.get_all_notices(audience)


@router.get("/all")
def list_notices_admin():
    return crud.get_all_notices_admin()


@router.post("", status_code=201)
def create_notice(data: NoticeCreate):
    return crud.create_notice(data.title.strip(), data.body.strip(), data.audience)


@router.put("/{notice_id}")
def update_notice(notice_id: str, data: NoticeUpdate):
    patch = {}
    if data.title    is not None: patch["title"]    = data.title.strip()
    if data.body     is not None: patch["body"]     = data.body.strip()
    if data.audience is not None: patch["audience"] = data.audience
    if data.active   is not None: patch["active"]   = data.active
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    return crud.update_notice(notice_id, patch)


@router.delete("/{notice_id}")
def delete_notice(notice_id: str):
    crud.delete_notice(notice_id)
    return {"status": "ok"}


@router.patch("/read")
def patch_read(body: ReadPatch):
    if body.user_type not in ("realtor", "coach"):
        raise HTTPException(status_code=400, detail="user_type must be 'realtor' or 'coach'.")
    read_notices = crud.patch_read_notice(body.user_id, body.user_type, body.notice_id, body.read)
    return {"read_notices": read_notices}
