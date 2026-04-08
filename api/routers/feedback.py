# api/routers/feedback.py — Feedback email endpoint
#
# POST /api/feedback
#   Body: { name: str, page: str, message: str }
#   Sends feedback email to jacques@creativrealty.com
#
# Required Railway environment variables:
#   SMTP_HOST  — e.g. smtp.gmail.com
#   SMTP_PORT  — e.g. 587
#   SMTP_USER  — sending email address
#   SMTP_PASS  — SMTP password or app password

import os
import smtplib
import logging
import threading
from email.mime.text import MIMEText

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

RECIPIENT = "jacques@creativrealty.com"


class FeedbackBody(BaseModel):
    name:    str
    page:    str
    message: str


def send_email_background(name: str, page: str, message: str):
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    pw   = os.getenv("SMTP_PASS", "")

    subject = f"MJ Realty Platform Feedback — {page}"
    text    = f"From: {name}\nPage: {page}\n\nMessage:\n{message}"

    if not (host and user and pw):
        logger.info("[feedback] SMTP not configured — printing to logs instead")
        logger.info("[feedback] Subject: %s", subject)
        logger.info("[feedback] Body: %s", text)
        return

    try:
        msg = MIMEText(text)
        msg["Subject"] = subject
        msg["From"]    = user
        msg["To"]      = RECIPIENT

        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, pw)
            smtp.sendmail(user, [RECIPIENT], msg.as_string())

        logger.info("[feedback] Email sent from %s (page: %s)", name, page)
    except Exception as exc:
        logger.error("[feedback] Failed to send email: %s", exc)


@router.post("")
def submit_feedback(body: FeedbackBody):
    t = threading.Thread(target=send_email_background, args=(body.name, body.page, body.message))
    t.daemon = True
    t.start()
    return {"status": "ok"}
