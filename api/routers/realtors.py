# api/routers/realtors.py — Realtor CRUD endpoints
#
# GET    /api/realtors              — list all realtors
# GET    /api/realtors/{id}         — get one realtor
# POST   /api/realtors              — add a new realtor
# PUT    /api/realtors/{id}         — update a realtor
# DELETE /api/realtors/{id}         — remove a realtor
# GET    /api/realtors/{id}/history — score history for one realtor

import os
import sys
import re
import uuid
import threading
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import crud
from .feedback import send_welcome_email

router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class NewRealtor(BaseModel):
    name:           str
    email:          str
    coaching_focus: Optional[str] = "General coaching"


class UpdateRealtor(BaseModel):
    name:               Optional[str]   = None
    email:              Optional[str]   = None
    coaching_focus:     Optional[str]   = None
    martin_goals:       Optional[str]   = None
    priorities:         Optional[str]   = None
    yearly_goals:       Optional[dict]  = None
    tasks:              Optional[list]  = None
    current_gci:        Optional[float] = None
    current_deals:      Optional[int]   = None
    current_buyers:     Optional[int]   = None
    current_sellers:    Optional[int]   = None
    last_goals_updated: Optional[str]   = None
    weekly_hours:       Optional[int]   = None
    experience_level:   Optional[str]   = None
    roadmap_completed:  Optional[list]  = None


class RoadmapPatch(BaseModel):
    item:      str
    completed: bool


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def get_realtors():
    return crud.get_all_realtors()


@router.get("/by-email/{email}")
def get_realtor_by_email_route(email: str):
    return crud.get_realtor_by_email(email)


@router.get("/{realtor_id}/history")
def get_realtor_history(realtor_id: str):
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found.")
    return {
        "realtor_id":   realtor_id,
        "realtor_name": realtor["name"],
        "score_history": realtor.get("score_history", []),
    }


@router.get("/{realtor_id}")
def get_realtor(realtor_id: str):
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found.")
    return realtor


@router.post("", status_code=201)
def add_realtor(data: NewRealtor):
    existing = crud.get_all_realtors()
    if any(r["email"] == data.email.strip().lower() for r in existing):
        raise HTTPException(status_code=409, detail="A realtor with that email already exists.")
    slug       = re.sub(r"[^a-z0-9]", "_", data.name.lower())
    realtor_id = f"realtor_{slug}_{uuid.uuid4().hex[:6]}"
    from config import init_realtor_tasks
    new_realtor = crud.create_realtor(
        realtor_id,
        data.name.strip(),
        data.email.strip().lower(),
        coaching_focus=(data.coaching_focus or "General coaching").strip(),
    )
    # Set default tasks via update (create_realtor sets empty list)
    default_tasks = init_realtor_tasks()
    result = crud.update_realtor(realtor_id, {"tasks": default_tasks})

    # Resolve coach name for the welcome email
    coach_name = "Your Coach"
    try:
        coach_id = (result or {}).get("coach_id")
        if coach_id:
            coach = crud.get_coach_by_id(coach_id)
            if coach and coach.get("name"):
                coach_name = coach["name"]
    except Exception:
        pass

    # Fire welcome email in background — non-blocking
    t = threading.Thread(
        target=send_welcome_email,
        args=(data.name.strip(), data.email.strip().lower(), coach_name),
        daemon=True,
    )
    t.start()

    return result


@router.put("/{realtor_id}")
def update_realtor(realtor_id: str, data: UpdateRealtor):
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found.")
    patch = {}
    if data.name               is not None: patch["name"]               = data.name.strip()
    if data.email              is not None: patch["email"]              = data.email.strip().lower()
    if data.coaching_focus     is not None: patch["coaching_focus"]     = data.coaching_focus.strip()
    if data.martin_goals       is not None: patch["martin_goals"]       = data.martin_goals.strip()
    if data.priorities         is not None: patch["priorities"]         = data.priorities.strip()
    if data.yearly_goals       is not None: patch["yearly_goals"]       = data.yearly_goals
    if data.tasks              is not None: patch["tasks"]              = data.tasks
    if data.current_gci        is not None: patch["current_gci"]        = data.current_gci
    if data.current_deals      is not None: patch["current_deals"]      = data.current_deals
    if data.current_buyers     is not None: patch["current_buyers"]     = data.current_buyers
    if data.current_sellers    is not None: patch["current_sellers"]    = data.current_sellers
    if data.last_goals_updated is not None: patch["last_goals_updated"] = data.last_goals_updated
    if data.weekly_hours       is not None: patch["weekly_hours"]       = data.weekly_hours
    if data.experience_level   is not None: patch["experience_level"]   = data.experience_level
    if data.roadmap_completed  is not None: patch["roadmap_completed"]  = data.roadmap_completed
    if not patch:
        return realtor
    return crud.update_realtor(realtor_id, patch)


@router.patch("/{realtor_id}/roadmap")
def patch_roadmap(realtor_id: str, data: RoadmapPatch):
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found.")
    completed: list = list(realtor.get("roadmap_completed") or [])
    if data.completed and data.item not in completed:
        completed.append(data.item)
    elif not data.completed and data.item in completed:
        completed.remove(data.item)
    crud.update_realtor(realtor_id, {"roadmap_completed": completed})
    return {"roadmap_completed": completed}


@router.delete("/{realtor_id}")
def delete_realtor(realtor_id: str):
    if not crud.get_realtor_by_id(realtor_id):
        raise HTTPException(status_code=404, detail="Realtor not found.")
    crud.delete_realtor(realtor_id)
    return {"status": "deleted", "id": realtor_id}
