# api/routers/admin.py — Super-admin endpoints (Jacques only, enforced at frontend)
#
# GET    /api/admin/coaches              — all coaches with embedded realtors
# GET    /api/admin/realtors             — all realtors with coach name + id
# POST   /api/admin/coaches              — create coach { name, email }
# DELETE /api/admin/coaches/{id}         — delete coach, unassign their realtors
# PATCH  /api/admin/coaches/{id}         — update { name?, email?, active? }
# POST   /api/admin/realtors             — create realtor { name, email, coach_id? }
# DELETE /api/admin/realtors/{id}        — delete realtor
# PATCH  /api/admin/realtors/{id}        — update { name?, email?, active? }
# POST   /api/admin/realtors/{id}/assign — { coach_id } assign/move realtor to coach

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

COACHES_PATH  = os.path.join(ROOT, "data", "coaches.json")
REALTORS_PATH = os.path.join(ROOT, "realtors.json")


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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_coaches() -> list[dict]:
    if not os.path.exists(COACHES_PATH):
        return []
    with open(COACHES_PATH) as f:
        data = json.load(f)
    coaches = data["coaches"] if isinstance(data, dict) else data
    # Ensure active field
    for c in coaches:
        c.setdefault("active", True)
    return coaches

def _save_coaches(coaches: list[dict]):
    os.makedirs(os.path.dirname(COACHES_PATH), exist_ok=True)
    with open(COACHES_PATH, "w") as f:
        json.dump({"coaches": coaches}, f, indent=2)

def _load_realtors() -> list[dict]:
    if not os.path.exists(REALTORS_PATH):
        return []
    with open(REALTORS_PATH) as f:
        data = json.load(f)
    realtors = data if isinstance(data, list) else data.get("realtors", [])
    for r in realtors:
        r.setdefault("active", True)
    return realtors

def _save_realtors(realtors: list[dict]):
    with open(REALTORS_PATH, "w") as f:
        json.dump(realtors, f, indent=2)

def _find(items: list[dict], item_id: str) -> Optional[dict]:
    return next((x for x in items if x["id"] == item_id), None)

def _coach_of(realtor_id: str, coaches: list[dict]) -> Optional[dict]:
    return next((c for c in coaches if realtor_id in c.get("realtor_ids", [])), None)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/coaches")
def list_coaches():
    coaches  = _load_coaches()
    realtors = _load_realtors()
    result   = []
    for c in coaches:
        ids = set(c.get("realtor_ids", []))
        result.append({
            **c,
            "realtors": [r for r in realtors if r["id"] in ids],
        })
    return result


@router.get("/realtors")
def list_realtors():
    coaches  = _load_coaches()
    realtors = _load_realtors()
    result   = []
    for r in realtors:
        coach = _coach_of(r["id"], coaches)
        result.append({
            **r,
            "coach_id":   coach["id"]   if coach else None,
            "coach_name": coach["name"] if coach else None,
        })
    return result


@router.post("/coaches", status_code=201)
def create_coach(data: CoachCreate):
    coaches = _load_coaches()
    if any(c["email"].lower() == data.email.strip().lower() for c in coaches):
        raise HTTPException(status_code=409, detail="A coach with that email already exists.")
    new_coach = {
        "id":          f"coach_{uuid.uuid4().hex[:8]}",
        "name":        data.name.strip(),
        "email":       data.email.strip().lower(),
        "active":      True,
        "realtor_ids": [],
    }
    coaches.append(new_coach)
    _save_coaches(coaches)
    return {**new_coach, "realtors": []}


@router.delete("/coaches/{coach_id}")
def delete_coach(coach_id: str):
    coaches = _load_coaches()
    coach   = _find(coaches, coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    # Unassign their realtors (keep the realtors, just remove from this coach's list)
    updated = [c for c in coaches if c["id"] != coach_id]
    _save_coaches(updated)
    return {"status": "deleted", "id": coach_id}


@router.patch("/coaches/{coach_id}")
def patch_coach(coach_id: str, data: CoachPatch):
    coaches = _load_coaches()
    coach   = _find(coaches, coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    if data.name   is not None: coach["name"]   = data.name.strip()
    if data.email  is not None: coach["email"]  = data.email.strip().lower()
    if data.active is not None: coach["active"] = data.active
    _save_coaches(coaches)
    realtors = _load_realtors()
    ids = set(coach.get("realtor_ids", []))
    return {**coach, "realtors": [r for r in realtors if r["id"] in ids]}


@router.post("/realtors", status_code=201)
def create_realtor(data: RealtorCreate):
    realtors = _load_realtors()
    if any(r["email"].lower() == data.email.strip().lower() for r in realtors):
        raise HTTPException(status_code=409, detail="A realtor with that email already exists.")
    new_id = f"realtor_{data.name.strip().lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}"
    new_realtor = {
        "id":             new_id,
        "name":           data.name.strip(),
        "email":          data.email.strip().lower(),
        "active":         True,
        "coaching_focus": "General coaching",
        "martin_goals":   "",
        "priorities":     "",
        "yearly_goals":   {
            "conservative_gci": 0, "stretch_gci": 0,
            "total_deals": 0, "buyer_deals": 0, "seller_deals": 0,
        },
        "tasks":          [],
        "score_history":  [],
        "folder_id":      "",
        "folder_url":     "",
        "current_gci":    0,
        "current_deals":  0,
        "current_buyers": 0,
        "current_sellers":0,
    }
    realtors.append(new_realtor)
    _save_realtors(realtors)

    # Assign to coach if provided
    coaches = _load_coaches()
    coach   = None
    if data.coach_id:
        coach = _find(coaches, data.coach_id)
        if coach:
            if new_id not in coach.get("realtor_ids", []):
                coach.setdefault("realtor_ids", []).append(new_id)
            _save_coaches(coaches)

    return {
        **new_realtor,
        "coach_id":   coach["id"]   if coach else None,
        "coach_name": coach["name"] if coach else None,
    }


@router.delete("/realtors/{realtor_id}")
def delete_realtor(realtor_id: str):
    realtors = _load_realtors()
    if not _find(realtors, realtor_id):
        raise HTTPException(status_code=404, detail="Realtor not found.")
    # Remove from any coach's realtor_ids
    coaches = _load_coaches()
    for c in coaches:
        c["realtor_ids"] = [r for r in c.get("realtor_ids", []) if r != realtor_id]
    _save_coaches(coaches)
    _save_realtors([r for r in realtors if r["id"] != realtor_id])
    return {"status": "deleted", "id": realtor_id}


@router.patch("/realtors/{realtor_id}")
def patch_realtor(realtor_id: str, data: RealtorPatch):
    realtors = _load_realtors()
    realtor  = _find(realtors, realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found.")
    if data.name   is not None: realtor["name"]   = data.name.strip()
    if data.email  is not None: realtor["email"]  = data.email.strip().lower()
    if data.active is not None: realtor["active"] = data.active
    _save_realtors(realtors)
    coaches = _load_coaches()
    coach   = _coach_of(realtor_id, coaches)
    return {
        **realtor,
        "coach_id":   coach["id"]   if coach else None,
        "coach_name": coach["name"] if coach else None,
    }


@router.post("/realtors/{realtor_id}/assign")
def assign_realtor(realtor_id: str, body: AssignBody):
    realtors = _load_realtors()
    if not _find(realtors, realtor_id):
        raise HTTPException(status_code=404, detail="Realtor not found.")
    coaches = _load_coaches()
    # Remove from any existing coach
    for c in coaches:
        c["realtor_ids"] = [r for r in c.get("realtor_ids", []) if r != realtor_id]
    # Assign to new coach
    new_coach = _find(coaches, body.coach_id)
    if not new_coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    new_coach.setdefault("realtor_ids", []).append(realtor_id)
    _save_coaches(coaches)
    realtor = _find(realtors, realtor_id)
    return {
        **realtor,
        "coach_id":   new_coach["id"],
        "coach_name": new_coach["name"],
    }
