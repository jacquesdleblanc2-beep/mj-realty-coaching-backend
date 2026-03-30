# api/routers/admin.py — Super-admin endpoints (Jacques only, enforced at frontend)
#
# GET    /api/admin/coaches              — all coaches with embedded realtors
# GET    /api/admin/realtors             — all realtors with coach name + id
# POST   /api/admin/coaches              — create coach { name, email }
# DELETE /api/admin/coaches/{id}         — delete coach, realtors' coach_id set to null
# PATCH  /api/admin/coaches/{id}         — update { name?, email?, active? }
# POST   /api/admin/realtors             — create realtor { name, email, coach_id? }
# DELETE /api/admin/realtors/{id}        — delete realtor
# PATCH  /api/admin/realtors/{id}        — update { name?, email?, active? }
# POST   /api/admin/realtors/{id}/assign — { coach_id } assign/move realtor to coach

import os
import sys
import re
import uuid
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import crud

router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────────

class CoachCreate(BaseModel):
    name:  str
    email: str

class CoachPatch(BaseModel):
    name:   Optional[str]  = None
    email:  Optional[str]  = None
    active: Optional[bool] = None

class RealtorCreate(BaseModel):
    name:     str
    email:    str
    coach_id: Optional[str] = None

class RealtorPatch(BaseModel):
    name:   Optional[str]  = None
    email:  Optional[str]  = None
    active: Optional[bool] = None

class AssignBody(BaseModel):
    coach_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/coaches")
def list_coaches():
    coaches  = crud.get_all_coaches()
    realtors = crud.get_all_realtors()
    r_by_coach: dict[str, list] = {}
    for r in realtors:
        cid = r.get("coach_id")
        if cid:
            r_by_coach.setdefault(cid, []).append(r)
    return [{**c, "realtors": r_by_coach.get(c["id"], [])} for c in coaches]


@router.get("/realtors")
def list_realtors():
    realtors = crud.get_all_realtors()
    coaches  = {c["id"]: c for c in crud.get_all_coaches()}
    result   = []
    for r in realtors:
        coach = coaches.get(r.get("coach_id", ""))
        result.append({
            **r,
            "coach_id":   coach["id"]   if coach else None,
            "coach_name": coach["name"] if coach else None,
        })
    return result


@router.post("/coaches", status_code=201)
def create_coach(data: CoachCreate):
    if crud.get_coach_by_email(data.email.strip()):
        raise HTTPException(status_code=409, detail="A coach with that email already exists.")
    coach_id = f"coach_{uuid.uuid4().hex[:8]}"
    coach    = crud.create_coach(coach_id, data.name.strip(), data.email.strip().lower())
    return {**coach, "realtors": []}


@router.delete("/coaches/{coach_id}")
def delete_coach(coach_id: str):
    if not crud.get_coach_by_id(coach_id):
        raise HTTPException(status_code=404, detail="Coach not found.")
    # Realtors' coach_id is set to NULL by the FK ON DELETE SET NULL in Supabase
    crud.delete_coach(coach_id)
    return {"status": "deleted", "id": coach_id}


@router.patch("/coaches/{coach_id}")
def patch_coach(coach_id: str, data: CoachPatch):
    coach = crud.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    patch = {}
    if data.name   is not None: patch["name"]   = data.name.strip()
    if data.email  is not None: patch["email"]  = data.email.strip().lower()
    if data.active is not None: patch["active"] = data.active
    updated  = crud.update_coach(coach_id, patch) if patch else coach
    realtors = crud.get_realtors_by_coach(coach_id)
    return {**updated, "realtors": realtors}


@router.post("/realtors", status_code=201)
def create_realtor(data: RealtorCreate):
    all_realtors = crud.get_all_realtors()
    if any(r["email"] == data.email.strip().lower() for r in all_realtors):
        raise HTTPException(status_code=409, detail="A realtor with that email already exists.")
    slug       = re.sub(r"[^a-z0-9]", "_", data.name.lower())
    realtor_id = f"realtor_{slug}_{uuid.uuid4().hex[:6]}"
    realtor    = crud.create_realtor(
        realtor_id,
        data.name.strip(),
        data.email.strip().lower(),
        coach_id=data.coach_id or None,
    )
    coach = crud.get_coach_by_id(data.coach_id) if data.coach_id else None
    return {
        **realtor,
        "coach_id":   coach["id"]   if coach else None,
        "coach_name": coach["name"] if coach else None,
    }


@router.delete("/realtors/{realtor_id}")
def delete_realtor(realtor_id: str):
    if not crud.get_realtor_by_id(realtor_id):
        raise HTTPException(status_code=404, detail="Realtor not found.")
    crud.delete_realtor(realtor_id)
    return {"status": "deleted", "id": realtor_id}


@router.patch("/realtors/{realtor_id}")
def patch_realtor(realtor_id: str, data: RealtorPatch):
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found.")
    patch = {}
    if data.name   is not None: patch["name"]   = data.name.strip()
    if data.email  is not None: patch["email"]  = data.email.strip().lower()
    if data.active is not None: patch["active"] = data.active
    updated = crud.update_realtor(realtor_id, patch) if patch else realtor
    coach   = crud.get_coach_by_id(updated.get("coach_id", "")) if updated.get("coach_id") else None
    return {
        **updated,
        "coach_id":   coach["id"]   if coach else None,
        "coach_name": coach["name"] if coach else None,
    }


@router.post("/realtors/{realtor_id}/assign")
def assign_realtor(realtor_id: str, body: AssignBody):
    if not crud.get_realtor_by_id(realtor_id):
        raise HTTPException(status_code=404, detail="Realtor not found.")
    coach = crud.get_coach_by_id(body.coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    updated = crud.update_realtor(realtor_id, {"coach_id": body.coach_id})
    return {
        **updated,
        "coach_id":   coach["id"],
        "coach_name": coach["name"],
    }
