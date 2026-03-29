# api/routers/pipeline.py — Pipeline trigger endpoints
#
# POST /api/pipeline/monday  — run full Monday pipeline (collect + create + email)
# POST /api/pipeline/sunday  — send Sunday reminder emails
# GET  /api/pipeline/status  — last run info from send_log.json

import os
import sys
import json

# Resolve imports back to the project root (one level up from api/)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional

router   = APIRouter()
LOG_PATH = os.path.join(ROOT, "send_log.json")


class PipelineOptions(BaseModel):
    dry_run: Optional[bool] = False


@router.post("/monday")
def run_monday(opts: PipelineOptions = PipelineOptions()):
    """
    Run the full Monday pipeline:
    collect last week's scores → build report → email Martin →
    create new sheets → email realtors.
    """
    from pipeline import run_monday_pipeline
    try:
        results = run_monday_pipeline(dry_run=opts.dry_run)
        return {"status": "ok", **results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sunday")
def run_sunday(opts: PipelineOptions = PipelineOptions()):
    """
    Send Sunday reminder emails to all realtors (sheet due tonight).
    """
    from pipeline import run_sunday_reminder
    try:
        results = run_sunday_reminder(dry_run=opts.dry_run)
        return {"status": "ok", **results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def pipeline_status():
    """Return the last log entry and total count from send_log.json."""
    if not os.path.exists(LOG_PATH):
        return {"last_run": None, "total_entries": 0}
    try:
        with open(LOG_PATH) as f:
            log = json.load(f)
        return {
            "last_run":      log[-1] if log else None,
            "total_entries": len(log),
            "recent":        log[-5:][::-1],  # last 5 entries, newest first
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
