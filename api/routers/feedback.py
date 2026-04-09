# api/routers/feedback.py — Feedback endpoints
#
# POST   /api/feedback              — submit feedback (stores + emails)
# GET    /api/feedback              — list all submissions (admin)
# DELETE /api/feedback/{id}         — delete a submission (admin)
#
# Required Railway env vars for email sending:
#   RESEND_API_KEY — Resend API key

import os
import logging
import threading
import urllib.request
import json

from fastapi import APIRouter
from pydantic import BaseModel
from .. import crud

router = APIRouter()
logger = logging.getLogger(__name__)
RECIPIENT = "jacques@creativrealty.com"


class FeedbackBody(BaseModel):
    name:    str
    page:    str
    message: str


def send_email_background(name: str, page: str, message: str):
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.info("[feedback] RESEND_API_KEY not set — logging only")
        logger.info("[feedback] From: %s | Page: %s | Message: %s", name, page, message)
        return
    try:
        payload = json.dumps({
            "from":    "MJ Realty Platform <noreply@creativrealty.com>",
            "to":      [RECIPIENT],
            "subject": f"MJ Realty Feedback — {page}",
            "text":    f"From: {name}\nPage: {page}\n\nMessage:\n{message}",
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "User-Agent":    "MJRealty-Platform/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("[feedback] Email sent via Resend, status: %s", resp.status)
    except Exception as exc:
        logger.error("[feedback] Resend failed: %s", exc)


@router.post("")
def submit_feedback(body: FeedbackBody):
    # Always store in Supabase first, then fire email in background
    try:
        crud.save_feedback(body.name, body.page, body.message)
    except Exception as exc:
        logger.error("[feedback] Failed to save to Supabase: %s", exc)

    t = threading.Thread(target=send_email_background, args=(body.name, body.page, body.message))
    t.daemon = True
    t.start()
    return {"status": "ok"}


@router.get("")
def list_feedback():
    return crud.get_all_feedback()


@router.delete("/{feedback_id}")
def remove_feedback(feedback_id: str):
    crud.delete_feedback(feedback_id)
    return {"status": "ok"}
