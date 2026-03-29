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
import json
from datetime import datetime
from typing import Any, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

PROGRESS_PATH = os.path.join(ROOT, "weekly_progress.json")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Pydantic models ────────────────────────────────────────────────────────────

class TaskPatch(BaseModel):
    task:   str
    # New-style actions
    action: Optional[str] = None   # "set_count" | "toggle_yes_no"
    day:    Optional[str] = None   # for set_count
    value:  Optional[int] = None   # for set_count
    # Legacy-style (used by history page)
    done:   Optional[bool] = None


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

def _load_all() -> list:
    if not os.path.exists(PROGRESS_PATH):
        return []
    try:
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def _save_all(data: list):
    with open(PROGRESS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _find_entry(all_data: list, realtor_id: str, week_label: str) -> Optional[dict]:
    for entry in all_data:
        if entry.get("realtor_id") == realtor_id and entry.get("week_label") == week_label:
            return entry
    return None


def _earned(t: dict) -> float:
    """Partial earned points for a task."""
    if not t.get("enabled", True):
        return 0.0
    if t.get("input_type", "yes_no") == "count":
        target = t.get("target", 1)
        total  = t.get("weekly_total", 0)
        return round(min(total / target, 1.0) * t["points"], 1) if target else 0.0
    else:
        return float(t["points"]) if t.get("done", False) else 0.0


def _calc_score(tasks: list) -> tuple[float, int, int]:
    score    = sum(_earned(t) for t in tasks if t.get("enabled", True))
    possible = sum(t["points"] for t in tasks if t.get("enabled", True))
    pct      = round((score / possible) * 100) if possible else 0
    return score, possible, pct


def _default_daily_counts() -> dict:
    return {d: 0 for d in DAYS}


def _default_tasks(realtor_id: str) -> list:
    from config import load_realtors
    realtors = load_realtors()
    realtor  = next((r for r in realtors if r["id"] == realtor_id), None)
    if not realtor:
        return []
    out = []
    for t in realtor.get("tasks", []):
        if not t.get("enabled", True):
            continue
        entry = {
            "category":   t.get("category", ""),
            "task":       t["task"],
            "points":     t["points"],
            "input_type": t.get("input_type", "yes_no"),
            "enabled":    True,
            "done":       False,
            "earned_points": 0.0,
        }
        if entry["input_type"] == "count":
            entry["target"]       = t.get("target", 1)
            entry["daily_counts"] = _default_daily_counts()
            entry["weekly_total"] = 0
        out.append(entry)
    return out


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


def _make_entry(realtor_id: str, week_label: str) -> dict:
    tasks                  = _default_tasks(realtor_id)
    score, possible, pct   = _calc_score(tasks)
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


# ── GET all weeks for a realtor ───────────────────────────────────────────────

@router.get("/{realtor_id}")
def get_all_progress(realtor_id: str):
    all_data = _load_all()
    return [e for e in all_data if e.get("realtor_id") == realtor_id]


# ── GET single week ────────────────────────────────────────────────────────────

@router.get("/{realtor_id}/{week_label}")
def get_progress(realtor_id: str, week_label: str):
    all_data = _load_all()
    entry    = _find_entry(all_data, realtor_id, week_label)
    if entry is None:
        entry = _make_entry(realtor_id, week_label)
    return entry


# ── POST (full save) ───────────────────────────────────────────────────────────

@router.post("/{realtor_id}/{week_label}")
def save_progress(realtor_id: str, week_label: str, body: FullProgress):
    all_data             = _load_all()
    score, possible, pct = _calc_score(body.tasks)
    entry                = _find_entry(all_data, realtor_id, week_label)

    updated = {
        "realtor_id":     realtor_id,
        "week_label":     week_label,
        "tasks":          body.tasks,
        "activity_log":   (entry or {}).get("activity_log", _default_activity()),
        "notes":          body.notes,
        "daily_focus":    (entry or {}).get("daily_focus", {}),
        "score":          score,
        "total_possible": possible,
        "percentage":     pct,
        "last_updated":   datetime.now().isoformat(),
    }

    if entry is None:
        all_data.append(updated)
    else:
        idx           = all_data.index(entry)
        all_data[idx] = updated

    _save_all(all_data)
    return updated


# ── PATCH (task update — count or yes_no) ─────────────────────────────────────

@router.patch("/{realtor_id}/{week_label}/task")
def patch_task(realtor_id: str, week_label: str, body: TaskPatch):
    all_data = _load_all()
    entry    = _find_entry(all_data, realtor_id, week_label)

    if entry is None:
        entry = _make_entry(realtor_id, week_label)
        all_data.append(entry)

    # Find the task
    t = next((x for x in entry["tasks"] if x["task"] == body.task), None)
    if t is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {body.task!r}")

    input_type = t.get("input_type", "yes_no")

    # ── Legacy toggle (used by history page) ──────────────────────────────────
    if body.action is None and body.done is not None:
        t["done"] = body.done
        t["earned_points"] = _earned(t)

    # ── New: set_count ────────────────────────────────────────────────────────
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
        weekly_total        = sum(t["daily_counts"].values())
        t["weekly_total"]   = weekly_total
        target              = t.get("target", 1)
        t["done"]           = weekly_total >= target
        t["earned_points"]  = _earned(t)

    # ── New: toggle_yes_no ────────────────────────────────────────────────────
    elif body.action == "toggle_yes_no":
        if input_type != "yes_no":
            raise HTTPException(status_code=400, detail="Task is not a yes/no task.")
        t["done"]          = not t.get("done", False)
        t["earned_points"] = _earned(t)

    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use set_count, toggle_yes_no, or provide done.")

    score, possible, pct    = _calc_score(entry["tasks"])
    entry["score"]          = score
    entry["total_possible"] = possible
    entry["percentage"]     = pct
    entry["last_updated"]   = datetime.now().isoformat()

    idx           = all_data.index(entry)
    all_data[idx] = entry
    _save_all(all_data)
    return entry


# ── POST /activity (single cell update) ───────────────────────────────────────

@router.post("/{realtor_id}/{week_label}/activity")
def update_activity(realtor_id: str, week_label: str, body: ActivityUpdate):
    all_data = _load_all()
    entry    = _find_entry(all_data, realtor_id, week_label)

    if entry is None:
        entry = _make_entry(realtor_id, week_label)
        all_data.append(entry)

    row = next((r for r in entry["activity_log"] if r["day"] == body.day), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Day not found: {body.day!r}")

    row[body.column]      = body.value
    entry["last_updated"] = datetime.now().isoformat()

    idx           = all_data.index(entry)
    all_data[idx] = entry
    _save_all(all_data)
    return {"status": "ok", "day": body.day, "column": body.column, "value": body.value}


# ── PATCH /daily (today's focus checkboxes) ────────────────────────────────────

@router.patch("/{realtor_id}/{week_label}/daily")
def update_daily_focus(realtor_id: str, week_label: str, body: DailyFocus):
    all_data = _load_all()
    entry    = _find_entry(all_data, realtor_id, week_label)

    if entry is None:
        entry = _make_entry(realtor_id, week_label)
        all_data.append(entry)

    if "daily_focus" not in entry:
        entry["daily_focus"] = {}

    entry["daily_focus"][body.date] = body.items
    entry["last_updated"]           = datetime.now().isoformat()

    idx           = all_data.index(entry)
    all_data[idx] = entry
    _save_all(all_data)
    return {"status": "ok", "date": body.date, "items": body.items}
