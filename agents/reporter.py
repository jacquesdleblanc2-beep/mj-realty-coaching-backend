# agents/reporter.py — Monday report collector

import os
import sys
import json
from datetime import datetime
from config import COACHING_CHECKLIST

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
from api import crud

from agents.sheets_manager import read_sheet_data

LOG_PATH      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "send_log.json")
PROGRESS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weekly_progress.json")


def _load_log() -> list:
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _load_progress() -> list:
    """Load weekly_progress.json (web dashboard checklist data)."""
    if os.path.exists(PROGRESS_PATH):
        try:
            with open(PROGRESS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _progress_for(realtor_id: str, week_label: str) -> dict | None:
    """Return the progress entry for a realtor + week, or None."""
    for entry in _load_progress():
        if entry.get("realtor_id") == realtor_id and entry.get("week_label") == week_label:
            return entry
    return None


def build_monday_report(week_label: str) -> dict:
    """
    Load the Sunday send log, read each realtor's sheet (or fall back to
    weekly_progress data if the dashboard was used instead), compile report.
    Also persists score history back to Supabase.
    """
    log     = _load_log()
    entries = []

    # Filter to last week's Monday send entries (sheets created that week)
    this_week = [e for e in log
                 if e.get("week_label") == week_label
                 and e.get("event") == "monday_send"]

    if not this_week:
        print(f"  Warning: no Monday send log found for '{week_label}'")

    # Build a quick lookup: realtor_id by name from Supabase
    realtors     = crud.get_all_realtors()
    id_by_name   = {r["name"]: r["id"] for r in realtors}

    for entry in this_week:
        sid   = entry.get("spreadsheet_id", "")
        url   = entry.get("sheet_url", "")
        name  = entry.get("realtor_name", "Unknown")
        rid   = id_by_name.get(name, "")

        print(f"  Reading data for {name}…")

        # ── Prefer weekly_progress (dashboard) over Google Sheets ────────────
        web_progress = _progress_for(rid, week_label) if rid else None

        if web_progress and web_progress.get("percentage", 0) > 0:
            print(f"    Using dashboard progress data for {name}")
            tasks      = web_progress.get("tasks", [])
            completed  = [t["task"] for t in tasks if t.get("done")]
            incomplete = [t["task"] for t in tasks if not t.get("done")]
            activity   = {
                row["day"]: {k: v for k, v in row.items() if k != "day"}
                for row in web_progress.get("activity_log", [])
            }
            data = {
                "score":           web_progress["score"],
                "total_possible":  web_progress["total_possible"],
                "percentage":      web_progress["percentage"],
                "completed":       completed,
                "incomplete":      incomplete,
                "activity_totals": activity,
                "note_to_martin":  "",
            }
            uploaded = True
        else:
            # Fall back to Google Sheets
            try:
                data     = read_sheet_data(sid)
                uploaded = len(data["completed"]) + len(data["incomplete"]) > 0
            except Exception as e:
                print(f"    Error reading sheet: {e}")
                data = {
                    "score": 0, "total_possible": 100, "percentage": 0,
                    "completed": [], "incomplete": [i["task"] for i in COACHING_CHECKLIST],
                    "activity_totals": {}, "note_to_martin": "",
                }
                uploaded = False

        entries.append({
            "realtor_name":    name,
            "realtor_email":   entry.get("realtor_email", ""),
            "sheet_url":       url,
            "uploaded":        uploaded,
            "score":           data["score"],
            "total_possible":  data["total_possible"],
            "percentage":      data["percentage"],
            "completed":       data["completed"],
            "incomplete":      data["incomplete"],
            "activity_totals": data["activity_totals"],
            "note_to_martin":  data["note_to_martin"],
        })

    # ── Persist score history to Supabase ─────────────────────────────────────
    for entry in entries:
        if not entry["uploaded"]:
            continue
        for r in realtors:
            if r["name"] == entry["realtor_name"]:
                history = [
                    h for h in (r.get("score_history") or [])
                    if h.get("week_label") != week_label
                ]
                history.append({
                    "week_label":     week_label,
                    "score":          entry["score"],
                    "total_possible": entry["total_possible"],
                    "percentage":     entry["percentage"],
                    "date":           datetime.now().strftime("%Y-%m-%d"),
                })
                crud.update_realtor(r["id"], {"score_history": history[-52:]})
                break

    return {
        "week_label":     week_label,
        "generated_at":   datetime.now().isoformat(),
        "total_realtors": len(entries),
        "submitted":      sum(1 for e in entries if e["uploaded"]),
        "entries":        entries,
    }
