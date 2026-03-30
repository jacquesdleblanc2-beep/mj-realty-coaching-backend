# api/routers/pipeline.py — Pipeline trigger endpoints
#
# POST /api/pipeline/monday  — run full Monday pipeline
# POST /api/pipeline/sunday  — send Sunday reminder emails
# GET  /api/pipeline/status  — recent send log entries

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import crud

router = APIRouter()


class PipelineOptions(BaseModel):
    dry_run: Optional[bool] = False


@router.post("/monday")
def run_monday(opts: PipelineOptions = PipelineOptions()):
    from pipeline import run_monday_pipeline
    try:
        results = run_monday_pipeline(dry_run=opts.dry_run)
        return {"status": "ok", **results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sunday")
def run_sunday(opts: PipelineOptions = PipelineOptions()):
    from pipeline import run_sunday_reminder
    try:
        results = run_sunday_reminder(dry_run=opts.dry_run)
        return {"status": "ok", **results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def pipeline_status():
    recent = crud.get_recent_log(limit=20)
    return {
        "last_run":      recent[0] if recent else None,
        "total_entries": len(recent),
        "recent":        recent[:5],
    }
