# api/routers/progress.py — Weekly checklist progress endpoints
#
# GET   /api/progress/{realtor_id}                        — all weeks for realtor
# GET   /api/progress/{realtor_id}/{week_label}           — load progress (create default if missing)
# POST  /api/progress/{realtor_id}/{week_label}           — save full progress
# PATCH /api/progress/{realtor_id}/{week_label}/task      — update one task (count or yes_no)
# POST  /api/progress/{realtor_id}/{week_label}/activity  — save one activity cell
# PATCH /api/progress/{realtor_id}/{week_label}/daily     — save daily focus checkboxes

import os
import sys
from datetime import datetime
from typing import Any, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import crud

router = APIRouter()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Pydantic models ────────────────────────────────────────────────────────────

class TaskPatch(BaseModel):
    task:   str
    action: Optional[str]  = None   # "set_count" | "toggle_yes_no"
    day:    Optional[str]  = None   # for set_count
    value:  Optional[int]  = None   # for set_count
    done:   Optional[bool] = None   # legacy (history page)


class ActivityUpdate(BaseModel):
    day:    str
    column: str
    value:  Any


class DailyFocus(BaseModel):
    date:  str
    items: list[bool]


class FullProgress(BaseModel):
    tasks: list[dict]
    notes: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _earned(t: dict) -> float:
    if not t.get("enabled", True):
        return 0.0
    if t.get("input_type", "yes_no") == "count":
        target = t.get("target", 1)
        total  = t.get("weekly_total", 0)
        return round(min(total / target, 1.0) * t["points"], 1) if target else 0.0
    return float(t["points"]) if t.get("done", False) else 0.0


def _calc_score(tasks: list) -> tuple[float, int, int]:
    score    = sum(_earned(t) for t in tasks if t.get("enabled", True))
    possible = sum(t["points"] for t in tasks if t.get("enabled", True))
    pct      = round((score / possible) * 100) if possible else 0
    return score, possible, pct


def _default_daily_counts() -> dict:
    return {d: 0 for d in DAYS}


def _default_activity() -> list:
    return [
        {
            "day":               day,
            "Prospecting":       0,
            "Listings / Buyers": 0,
            "Follow-Up":         0,
            "Social / Brand":    0,
            "Education":         0,
            "Notes / Wins":      "",
        }
        for day in DAYS
    ]


def _default_tasks(realtor_id: str) -> list:
    realtor = crud.get_realtor_by_id(realtor_id)
    if not realtor:
        return []
    out = []
    for t in (realtor.get("tasks") or []):
        if not t.get("enabled", True):
            continue
        entry = {
            "category":      t.get("category", ""),
            "task":          t["task"],
            "points":        t["points"],
            "input_type":    t.get("input_type", "yes_no"),
            "enabled":       True,
            "done":          False,
            "earned_points": 0.0,
        }
        if entry["input_type"] == "count":
            entry["target"]       = t.get("target", 1)
            entry["daily_counts"] = _default_daily_counts()
            entry["weekly_total"] = 0
        out.append(entry)
    return out


def _make_entry(realtor_id: str, week_label: str) -> dict:
    tasks                = _default_tasks(realtor_id)
    score, possible, pct = _calc_score(tasks)
    return {
        "realtor_id":     realtor_id,
        "week_label":     week_label,
        "tasks":          tasks,
        "activity_log":   _default_activity(),
        "notes":          "",
        "daily_focus":    {},
        "score":          score,
        "total_possible": possible,
        "percentage":     pct,
        "last_updated":   datetime.now().isoformat(),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/{realtor_id}")
def get_all_progress(realtor_id: str):
    return crud.get_all_progress(realtor_id)


@router.get("/{realtor_id}/{week_label}")
def get_progress(realtor_id: str, week_label: str):
    entry = crud.get_progress(realtor_id, week_label)
    if entry is None:
        entry = _make_entry(realtor_id, week_label)
    return entry


@router.post("/{realtor_id}/{week_label}")
def save_progress(realtor_id: str, week_label: str, body: FullProgress):
    existing             = crud.get_progress(realtor_id, week_label)
    score, possible, pct = _calc_score(body.tasks)
    updated = {
        "tasks":          body.tasks,
        "activity_log":   (existing or {}).get("activity_log", _default_activity()),
        "notes":          body.notes,
        "daily_focus":    (existing or {}).get("daily_focus", {}),
        "score":          score,
        "total_possible": possible,
        "percentage":     pct,
        "last_updated":   datetime.now().isoformat(),
    }
    return crud.upsert_progress(realtor_id, week_label, updated)


@router.patch("/{realtor_id}/{week_label}/task")
def patch_task(realtor_id: str, week_label: str, body: TaskPatch):
    entry = crud.get_progress(realtor_id, week_label)
    if entry is None:
        entry = _make_entry(realtor_id, week_label)

    tasks      = list(entry.get("tasks", []))
    t          = next((x for x in tasks if x["task"] == body.task), None)
    if t is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {body.task!r}")

    input_type = t.get("input_type", "yes_no")

    if body.action is None and body.done is not None:
        t["done"]          = body.done
        t["earned_points"] = _earned(t)

    elif body.action == "set_count":
        if input_type != "count":
            raise HTTPException(status_code=400, detail="Task is not a count task.")
        if t.get("done", False):
            raise HTTPException(status_code=400, detail="Task already completed — count is locked.")
        if body.day not in DAYS:
            raise HTTPException(status_code=400, detail=f"Invalid day: {body.day!r}")
        if body.value is None or body.value < 0:
            raise HTTPException(status_code=400, detail="value must be a non-negative integer.")
        if "daily_counts" not in t:
            t["daily_counts"] = _default_daily_counts()
        t["daily_counts"][body.day] = body.value
        weekly_total       = sum(t["daily_counts"].values())
        t["weekly_total"]  = weekly_total
        t["done"]          = weekly_total >= t.get("target", 1)
        t["earned_points"] = _earned(t)

    elif body.action == "toggle_yes_no":
        if input_type != "yes_no":
            raise HTTPException(status_code=400, detail="Task is not a yes/no task.")
        t["done"]          = not t.get("done", False)
        t["earned_points"] = _earned(t)

    else:
        raise HTTPException(status_code=400, detail="Invalid action.")

    score, possible, pct = _calc_score(tasks)
    return crud.upsert_progress(realtor_id, week_label, {
        "tasks":          tasks,
        "activity_log":   entry.get("activity_log", _default_activity()),
        "notes":          entry.get("notes", ""),
        "daily_focus":    entry.get("daily_focus", {}),
        "score":          score,
        "total_possible": possible,
        "percentage":     pct,
        "last_updated":   datetime.now().isoformat(),
    })


@router.post("/{realtor_id}/{week_label}/activity")
def update_activity(realtor_id: str, week_label: str, body: ActivityUpdate):
    entry = crud.get_progress(realtor_id, week_label)
    if entry is None:
        entry = _make_entry(realtor_id, week_label)

    activity = list(entry.get("activity_log", _default_activity()))
    row      = next((r for r in activity if r["day"] == body.day), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Day not found: {body.day!r}")

    row[body.column] = body.value
    crud.upsert_progress(realtor_id, week_label, {
        **entry,
        "activity_log": activity,
        "last_updated": datetime.now().isoformat(),
    })
    return {"status": "ok", "day": body.day, "column": body.column, "value": body.value}


@router.patch("/{realtor_id}/{week_label}/daily")
def update_daily_focus(realtor_id: str, week_label: str, body: DailyFocus):
    entry = crud.get_progress(realtor_id, week_label)
    if entry is None:
        entry = _make_entry(realtor_id, week_label)

    daily_focus = dict(entry.get("daily_focus") or {})
    daily_focus[body.date] = body.items
    crud.upsert_progress(realtor_id, week_label, {
        **entry,
        "daily_focus":  daily_focus,
        "last_updated": datetime.now().isoformat(),
    })
    return {"status": "ok", "date": body.date, "items": body.items}
