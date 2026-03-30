# api/routers/coaches.py — Coach management endpoints
#
# GET    /api/coaches                              — list all coaches
# GET    /api/coaches/by-email/{email}             — find coach by email
# GET    /api/coaches/{id}                         — get one coach
# POST   /api/coaches                              — create a coach
# PUT    /api/coaches/{id}                         — update coach fields
# DELETE /api/coaches/{id}                         — remove coach
# GET    /api/coaches/{id}/realtors                — full realtor objects for this coach
# POST   /api/coaches/{id}/realtors/{realtor_id}   — assign realtor to coach
# DELETE /api/coaches/{id}/realtors/{realtor_id}   — remove realtor from coach

import os
import sys
import json
import uuid
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

COACHES_PATH = os.path.join(ROOT, "data", "coaches.json")


# ── Pydantic models ────────────────────────────────────────────────────────────

class CoachCreate(BaseModel):
    name:  str
    email: str


class CoachUpdate(BaseModel):
    name:  Optional[str] = None
    email: Optional[str] = None


class Coach(BaseModel):
    id:          str
    name:        str
    email:       str
    realtor_ids: list[str] = []


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if not os.path.exists(COACHES_PATH):
        os.makedirs(os.path.dirname(COACHES_PATH), exist_ok=True)
        _save([])
        return []
    with open(COACHES_PATH) as f:
        data = json.load(f)
    # Support both {"coaches": [...]} and bare list
    return data["coaches"] if isinstance(data, dict) else data


def _save(coaches: list[dict]):
    os.makedirs(os.path.dirname(COACHES_PATH), exist_ok=True)
    with open(COACHES_PATH, "w") as f:
        json.dump({"coaches": coaches}, f, indent=2)


def _find(coaches: list[dict], coach_id: str) -> Optional[dict]:
    return next((c for c in coaches if c["id"] == coach_id), None)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def list_coaches():
    return _load()


@router.get("/by-email/{email}")
def get_coach_by_email(email: str):
    coaches = _load()
    for coach in coaches:
        if coach["email"].lower() == email.lower():
            return coach
    return None  # 200 with null body — lets frontend check without throwing


@router.get("/{coach_id}")
def get_coach(coach_id: str):
    coach = _find(_load(), coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    return coach


@router.post("", status_code=201)
def create_coach(data: CoachCreate):
    coaches = _load()
    if any(c["email"].lower() == data.email.strip().lower() for c in coaches):
        raise HTTPException(status_code=409, detail="A coach with that email already exists.")
    new_coach = {
        "id":          f"coach_{uuid.uuid4().hex[:8]}",
        "name":        data.name.strip(),
        "email":       data.email.strip().lower(),
        "realtor_ids": [],
    }
    coaches.append(new_coach)
    _save(coaches)
    return new_coach


@router.put("/{coach_id}")
def update_coach(coach_id: str, data: CoachUpdate):
    coaches = _load()
    coach = _find(coaches, coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    if data.name  is not None: coach["name"]  = data.name.strip()
    if data.email is not None: coach["email"] = data.email.strip().lower()
    _save(coaches)
    return coach


@router.delete("/{coach_id}")
def delete_coach(coach_id: str):
    coaches = _load()
    updated = [c for c in coaches if c["id"] != coach_id]
    if len(updated) == len(coaches):
        raise HTTPException(status_code=404, detail="Coach not found.")
    _save(updated)
    return {"status": "deleted", "id": coach_id}


@router.get("/{coach_id}/realtors")
def get_coach_realtors(coach_id: str):
    coach = _find(_load(), coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    from config import load_realtors
    all_realtors = load_realtors()
    ids = set(coach.get("realtor_ids", []))
    return [r for r in all_realtors if r["id"] in ids]


@router.post("/{coach_id}/realtors/{realtor_id}", status_code=201)
def assign_realtor(coach_id: str, realtor_id: str):
    coaches = _load()
    coach = _find(coaches, coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    if realtor_id not in coach["realtor_ids"]:
        coach["realtor_ids"].append(realtor_id)
        _save(coaches)
    return coach


@router.delete("/{coach_id}/realtors/{realtor_id}")
def remove_realtor(coach_id: str, realtor_id: str):
    coaches = _load()
    coach = _find(coaches, coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    if realtor_id not in coach.get("realtor_ids", []):
        raise HTTPException(status_code=404, detail="Realtor not assigned to this coach.")
    coach["realtor_ids"] = [r for r in coach["realtor_ids"] if r != realtor_id]
    _save(coaches)
    return coach
