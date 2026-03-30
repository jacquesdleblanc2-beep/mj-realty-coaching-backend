# api/routers/coaches.py — Coach management endpoints
#
# GET    /api/coaches                              — list all coaches
# GET    /api/coaches/by-email/{email}             — find coach by email (null if missing)
# GET    /api/coaches/{id}                         — get one coach
# POST   /api/coaches                              — create a coach
# PUT    /api/coaches/{id}                         — update coach fields
# DELETE /api/coaches/{id}                         — remove coach
# GET    /api/coaches/{id}/realtors                — full realtor objects for this coach
# POST   /api/coaches/{id}/realtors/{realtor_id}   — assign realtor to coach
# DELETE /api/coaches/{id}/realtors/{realtor_id}   — remove realtor from coach

import os
import sys
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


class CoachUpdate(BaseModel):
    name:  Optional[str] = None
    email: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def list_coaches():
    return crud.get_all_coaches()


@router.get("/by-email/{email}")
def get_coach_by_email(email: str):
    return crud.get_coach_by_email(email)  # None → 200 null, not 404


@router.get("/{coach_id}")
def get_coach(coach_id: str):
    coach = crud.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    return coach


@router.post("", status_code=201)
def create_coach(data: CoachCreate):
    existing = crud.get_coach_by_email(data.email.strip())
    if existing:
        raise HTTPException(status_code=409, detail="A coach with that email already exists.")
    coach_id = f"coach_{uuid.uuid4().hex[:8]}"
    return crud.create_coach(coach_id, data.name.strip(), data.email.strip().lower())


@router.put("/{coach_id}")
def update_coach(coach_id: str, data: CoachUpdate):
    coach = crud.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    patch = {}
    if data.name  is not None: patch["name"]  = data.name.strip()
    if data.email is not None: patch["email"] = data.email.strip().lower()
    if not patch:
        return coach
    return crud.update_coach(coach_id, patch)


@router.delete("/{coach_id}")
def delete_coach(coach_id: str):
    coach = crud.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    crud.delete_coach(coach_id)
    return {"status": "deleted", "id": coach_id}


@router.get("/{coach_id}/realtors")
def get_coach_realtors(coach_id: str):
    coach = crud.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    return crud.get_realtors_by_coach(coach_id)


@router.post("/{coach_id}/realtors/{realtor_id}", status_code=201)
def assign_realtor(coach_id: str, realtor_id: str):
    coach = crud.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found.")
    crud.update_realtor(realtor_id, {"coach_id": coach_id})
    return crud.get_coach_by_id(coach_id)


@router.delete("/{coach_id}/realtors/{realtor_id}")
def remove_realtor(coach_id: str, realtor_id: str):
    coach = crud.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor or realtor.get("coach_id") != coach_id:
        raise HTTPException(status_code=404, detail="Realtor not assigned to this coach.")
    crud.update_realtor(realtor_id, {"coach_id": None})
    return crud.get_coach_by_id(coach_id)
