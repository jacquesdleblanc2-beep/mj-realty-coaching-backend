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


@router.post("")
def send_feedback(body: FeedbackBody):
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    pw   = os.getenv("SMTP_PASS", "")

    subject = f"MJ Realty Platform Feedback — {body.page}"
    text    = f"From: {body.name}\nPage: {body.page}\n\nMessage:\n{body.message}"

    if not (host and user and pw):
        logger.info("[feedback] SMTP not configured — printing to logs instead")
        logger.info("[feedback] Subject: %s", subject)
        logger.info("[feedback] Body: %s", text)
        return {"status": "ok"}

    try:
        msg = MIMEText(text)
        msg["Subject"] = subject
        msg["From"]    = user
        msg["To"]      = RECIPIENT

        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, pw)
            smtp.sendmail(user, [RECIPIENT], msg.as_string())

        logger.info("[feedback] Email sent from %s (page: %s)", body.name, body.page)
    except Exception as exc:
        logger.error("[feedback] Failed to send email: %s", exc)

    return {"status": "ok"}
