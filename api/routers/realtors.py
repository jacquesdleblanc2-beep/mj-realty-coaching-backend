# api/routers/realtors.py — Realtor CRUD endpoints
#
# GET    /api/realtors              — list all realtors
# POST   /api/realtors              — add a new realtor
# PUT    /api/realtors/{id}         — update a realtor
# DELETE /api/realtors/{id}         — remove a realtor
# GET    /api/realtors/{id}/history — score history for one realtor

import os
import sys
import re
import uuid
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class NewRealtor(BaseModel):
    name:           str
    email:          str
    coaching_focus: Optional[str] = "General coaching"


class UpdateRealtor(BaseModel):
    name:               Optional[str]  = None
    email:              Optional[str]  = None
    coaching_focus:     Optional[str]  = None
    martin_goals:       Optional[str]  = None
    priorities:         Optional[str]  = None
    yearly_goals:       Optional[dict] = None
    tasks:              Optional[list] = None
    current_gci:        Optional[int]  = None
    current_deals:      Optional[int]  = None
    current_buyers:     Optional[int]  = None
    current_sellers:    Optional[int]  = None
    last_goals_updated: Optional[str]  = None


class YearlyGoals(BaseModel):
    conservative_gci: Optional[int] = 0
    stretch_gci:      Optional[int] = 0
    total_deals:      Optional[int] = 0
    buyer_deals:      Optional[int] = 0
    seller_deals:     Optional[int] = 0


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def get_realtors():
    """Return all realtors from realtors.json."""
    from config import load_realtors
    return load_realtors()


@router.post("", status_code=201)
def add_realtor(data: NewRealtor):
    """Add a new realtor. Does not create a Drive folder (use dashboard for that)."""
    from config import load_realtors, save_realtors, init_realtor_tasks
    realtors = load_realtors()

    # Check for duplicate email
    if any(r["email"] == data.email.strip().lower() for r in realtors):
        raise HTTPException(status_code=409, detail="A realtor with that email already exists.")

    slug = re.sub(r"[^a-z0-9]", "_", data.name.lower())
    new_realtor = {
        "id":             f"realtor_{slug}_{uuid.uuid4().hex[:6]}",
        "name":           data.name.strip(),
        "email":          data.email.strip().lower(),
        "coaching_focus": (data.coaching_focus or "General coaching").strip(),
        "martin_goals":   "",
        "priorities":     "",
        "yearly_goals":   {
            "conservative_gci": 0,
            "stretch_gci":      0,
            "total_deals":      0,
            "buyer_deals":      0,
            "seller_deals":     0,
        },
        "tasks":         init_realtor_tasks(),
        "score_history": [],
        "folder_id":     "",
        "folder_url":    "",
    }
    realtors.append(new_realtor)
    save_realtors(realtors)
    return new_realtor


@router.get("/{realtor_id}")
def get_realtor(realtor_id: str):
    from config import load_realtors
    realtors = load_realtors()
    for r in realtors:
        if r["id"] == realtor_id:
            return r
    raise HTTPException(status_code=404, detail="Realtor not found.")


@router.put("/{realtor_id}")
def update_realtor(realtor_id: str, data: UpdateRealtor):
    """Update name, email, focus, goals, priorities, or yearly targets."""
    from config import load_realtors, save_realtors
    realtors = load_realtors()

    for r in realtors:
        if r["id"] == realtor_id:
            if data.name               is not None: r["name"]               = data.name.strip()
            if data.email              is not None: r["email"]              = data.email.strip().lower()
            if data.coaching_focus     is not None: r["coaching_focus"]     = data.coaching_focus.strip()
            if data.martin_goals       is not None: r["martin_goals"]       = data.martin_goals.strip()
            if data.priorities         is not None: r["priorities"]         = data.priorities.strip()
            if data.yearly_goals       is not None: r["yearly_goals"]       = data.yearly_goals
            if data.tasks              is not None: r["tasks"]              = data.tasks
            if data.current_gci        is not None: r["current_gci"]        = data.current_gci
            if data.current_deals      is not None: r["current_deals"]      = data.current_deals
            if data.current_buyers     is not None: r["current_buyers"]     = data.current_buyers
            if data.current_sellers    is not None: r["current_sellers"]    = data.current_sellers
            if data.last_goals_updated is not None: r["last_goals_updated"] = data.last_goals_updated
            save_realtors(realtors)
            return r

    raise HTTPException(status_code=404, detail="Realtor not found.")


@router.delete("/{realtor_id}")
def delete_realtor(realtor_id: str):
    """Remove a realtor permanently."""
    from config import load_realtors, save_realtors
    realtors = load_realtors()
    updated  = [r for r in realtors if r["id"] != realtor_id]

    if len(updated) == len(realtors):
        raise HTTPException(status_code=404, detail="Realtor not found.")

    save_realtors(updated)
    return {"status": "deleted", "id": realtor_id}


@router.get("/{realtor_id}/history")
def get_history(realtor_id: str):
    """Return the full score history for one realtor."""
    from config import load_realtors
    realtors = load_realtors()

    for r in realtors:
        if r["id"] == realtor_id:
            return {
                "realtor_id":    r["id"],
                "realtor_name":  r["name"],
                "score_history": r.get("score_history", []),
            }

    raise HTTPException(status_code=404, detail="Realtor not found.")
