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


PLATFORM_URL = "https://mj-realty-coaching-frontend.vercel.app"


def _resend(payload: dict, log_tag: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.info("[%s] RESEND_API_KEY not set — skipping send", log_tag)
        return
    try:
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "User-Agent":    "MJRealty-Platform/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("[%s] Email sent via Resend, status: %s", log_tag, resp.status)
    except Exception as exc:
        logger.error("[%s] Resend failed: %s", log_tag, exc)


def send_email_background(name: str, page: str, message: str):
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.info("[feedback] RESEND_API_KEY not set — logging only")
        logger.info("[feedback] From: %s | Page: %s | Message: %s", name, page, message)
        return
    _resend({
        "from":    "MJ Realty Coaching <noreply@creativrealty.com>",
        "to":      [RECIPIENT],
        "subject": f"MJ Realty Feedback — {page}",
        "text":    f"From: {name}\nPage: {page}\n\nMessage:\n{message}",
    }, "feedback")


def send_welcome_email(name: str, email: str, coach_name: str = "Your Coach"):
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0fafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fafa;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #b2d8db;">

        <!-- Header -->
        <tr>
          <td style="background:#0D5C63;padding:28px 40px;">
            <p style="margin:0;color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">MJ Realty Coaching</p>
            <p style="margin:4px 0 0;color:#a7d8dc;font-size:13px;">Your coaching platform is ready</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;">Hi {name},</p>
            <p style="margin:0 0 16px;color:#374151;font-size:14px;line-height:1.6;">
              Your coaching account is ready. Here's everything you need to get started.
            </p>

            <!-- CTA button -->
            <table cellpadding="0" cellspacing="0" style="margin:24px 0;">
              <tr>
                <td style="background:#FF6B35;border-radius:8px;">
                  <a href="{PLATFORM_URL}"
                     style="display:inline-block;padding:12px 28px;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;">
                    Log in to your dashboard →
                  </a>
                </td>
              </tr>
            </table>

            <p style="margin:0 0 8px;color:#374151;font-size:13px;line-height:1.5;">
              Use the Google account linked to this email address to sign in.
            </p>

            <!-- Divider -->
            <hr style="border:none;border-top:1px solid #e5f0f1;margin:28px 0;">

            <p style="margin:0 0 10px;color:#0D5C63;font-size:13px;font-weight:600;">What to expect</p>
            <ul style="margin:0 0 20px;padding-left:20px;color:#374151;font-size:13px;line-height:1.8;">
              <li>Your coach has set up your profile and weekly tasks</li>
              <li>Every Monday morning your weekly checklist resets — that's your weekly scorecard</li>
              <li>Check your <strong>Dashboard</strong> to track your progress, goals, and performance over time</li>
              <li>Head to <strong>My Roadmap</strong> to see your career milestones</li>
              <li>Check the <strong>Notices</strong> tab in your sidebar for important updates and announcements from your coaching team</li>
            </ul>

            <p style="margin:0 0 10px;color:#0D5C63;font-size:13px;font-weight:600;">Your first week</p>
            <p style="margin:0 0 20px;color:#374151;font-size:13px;line-height:1.6;">
              Check in Monday morning — your first weekly checklist will be waiting for you.
              Fill in your daily activity counts and check off completed tasks throughout the week.
            </p>

            <p style="margin:0 0 28px;color:#374151;font-size:13px;line-height:1.6;">
              If you have any questions reach out to your coach directly.
            </p>

            <p style="margin:0;color:#374151;font-size:13px;line-height:1.6;">
              Welcome to the team — let's build something great.<br><br>
              <strong style="color:#0D5C63;">{coach_name}</strong><br>
              <span style="color:#6b7280;">MJ Realty Coaching</span>
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f0fafa;padding:20px 40px;border-top:1px solid #e5f0f1;">
            <p style="margin:0;color:#9ca3af;font-size:11px;text-align:center;">
              MJ Realty Coaching &bull; You received this because a coaching account was created for your email address.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    _resend({
        "from":    "MJ Realty Coaching <noreply@creativrealty.com>",
        "to":      [email],
        "subject": f"Welcome to MJ Realty Coaching, {name} \u2014 You\u2019re all set!",
        "html":    html,
    }, "welcome")


def send_coach_welcome_email(name: str, email: str):
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0fafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fafa;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #b2d8db;">

        <!-- Header -->
        <tr>
          <td style="background:#0D5C63;padding:28px 40px;">
            <p style="margin:0;color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">MJ Realty Coaching</p>
            <p style="margin:4px 0 0;color:#a7d8dc;font-size:13px;">Welcome to MJ Realty Coaching</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;">Hi {name},</p>
            <p style="margin:0 0 16px;color:#374151;font-size:14px;line-height:1.6;">
              Your coach account on the MJ Realty Coaching Platform is set up and ready to go.
            </p>

            <!-- CTA button -->
            <table cellpadding="0" cellspacing="0" style="margin:24px 0;">
              <tr>
                <td style="background:#FF6B35;border-radius:8px;">
                  <a href="{PLATFORM_URL}"
                     style="display:inline-block;padding:12px 28px;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;">
                    Log In to Your Dashboard →
                  </a>
                </td>
              </tr>
            </table>

            <!-- Divider -->
            <hr style="border:none;border-top:1px solid #e5f0f1;margin:28px 0;">

            <p style="margin:0 0 10px;color:#0D5C63;font-size:13px;font-weight:600;">As a coach, here's what you can do</p>
            <ul style="margin:0 0 20px;padding-left:20px;color:#374151;font-size:13px;line-height:1.8;">
              <li>View your full team overview and each realtor's weekly score</li>
              <li>Set weekly goals and tasks for each of your realtors</li>
              <li>Preview any realtor's dashboard exactly as they see it</li>
              <li>Send notices and important updates to your team</li>
              <li>Track performance trends over time</li>
            </ul>

            <p style="margin:0 0 10px;color:#0D5C63;font-size:13px;font-weight:600;">Getting started</p>
            <ul style="margin:0 0 28px;padding-left:20px;color:#374151;font-size:13px;line-height:1.8;">
              <li>Head to <strong>My Realtors</strong> to see your assigned team</li>
              <li>Click on any realtor to set their weekly strategy</li>
              <li>Use <strong>Notices</strong> to send your first team announcement</li>
            </ul>

            <p style="margin:0 0 8px;color:#374151;font-size:13px;line-height:1.6;">
              If you have any questions reach out to Jacques directly.
            </p>
            <p style="margin:0 0 28px;color:#374151;font-size:13px;line-height:1.6;">
              Welcome aboard — let's build a great team.
            </p>

            <p style="margin:0;color:#374151;font-size:13px;line-height:1.6;">
              <strong style="color:#0D5C63;">Jacques LeBlanc</strong><br>
              <span style="color:#6b7280;">MJ Realty Coaching</span>
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f0fafa;padding:20px 40px;border-top:1px solid #e5f0f1;">
            <p style="margin:0;color:#9ca3af;font-size:11px;text-align:center;">
              MJ Realty Coaching &bull; You received this because a coach account was created for your email address.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    _resend({
        "from":    "MJ Realty Coaching <noreply@creativrealty.com>",
        "to":      [email],
        "subject": f"Welcome to MJ Realty Coaching \u2014 Your Coach Account is Ready, {name}!",
        "html":    html,
    }, "coach-welcome")


def send_sunday_reminder_email(name: str, email: str, coach_name: str = "Your Coach"):
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0fafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fafa;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #b2d8db;">

        <!-- Header -->
        <tr>
          <td style="background:#0D5C63;padding:28px 40px;">
            <p style="margin:0;color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">MJ Realty Coaching</p>
            <p style="margin:4px 0 0;color:#a7d8dc;font-size:13px;">Weekly Check-In</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;">Hi {name},</p>
            <p style="margin:0 0 16px;color:#374151;font-size:14px;line-height:1.6;">
              Your weekly checklist closes tonight at midnight. Take 5 minutes to make sure it reflects
              your actual week — every call, every follow-up, every connection counts toward your score.
            </p>
            <p style="margin:0 0 24px;color:#374151;font-size:14px;line-height:1.6;">
              Don&apos;t leave points on the table. Log in and finish strong.
            </p>

            <!-- CTA button -->
            <table cellpadding="0" cellspacing="0" style="margin:0 0 32px;">
              <tr>
                <td style="background:#FF6B35;border-radius:8px;">
                  <a href="{PLATFORM_URL}"
                     style="display:inline-block;padding:12px 28px;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;">
                    Update My Checklist →
                  </a>
                </td>
              </tr>
            </table>

            <p style="margin:0;color:#374151;font-size:13px;line-height:1.6;">
              <strong style="color:#0D5C63;">{coach_name}</strong>
              <span style="color:#6b7280;"> &bull; MJ Realty Coaching</span>
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f0fafa;padding:20px 40px;border-top:1px solid #e5f0f1;">
            <p style="margin:0;color:#9ca3af;font-size:11px;text-align:center;">
              MJ Realty Coaching &bull; Weekly Sunday reminder.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    _resend({
        "from":    "MJ Realty Coaching <noreply@creativrealty.com>",
        "to":      [email],
        "subject": f"How did your week go, {name}?",
        "html":    html,
    }, "sunday-reminder")


def send_monday_new_week_email(name: str, email: str, coach_name: str = "Your Coach"):
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0fafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fafa;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #b2d8db;">

        <!-- Header -->
        <tr>
          <td style="background:#0D5C63;padding:28px 40px;">
            <p style="margin:0;color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">MJ Realty Coaching</p>
            <p style="margin:4px 0 0;color:#a7d8dc;font-size:13px;">New Week Starts Today</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;">Hi {name},</p>
            <p style="margin:0 0 16px;color:#374151;font-size:14px;line-height:1.6;">
              A fresh week starts today. Your checklist has been reset and your coach has set your
              targets for the week ahead.
            </p>
            <p style="margin:0 0 24px;color:#374151;font-size:14px;line-height:1.6;">
              Log in this morning, review your goals, and hit the ground running.
            </p>

            <!-- CTA button -->
            <table cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
              <tr>
                <td style="background:#FF6B35;border-radius:8px;">
                  <a href="{PLATFORM_URL}"
                     style="display:inline-block;padding:12px 28px;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;">
                    View My Week →
                  </a>
                </td>
              </tr>
            </table>

            <!-- Missed last week callout -->
            <div style="margin-top:24px;padding:16px;background:#f9f9f9;border-radius:8px;border:1px solid #eee;">
              <p style="font-size:13px;color:#888;margin:0;">
                <strong style="color:#666;">Missed last week&apos;s data entry?</strong>
                Log into your account and go to <strong>My Week &rarr; History</strong> to update your
                previous week&apos;s activity before it&apos;s too late.
              </p>
            </div>

            <p style="margin:32px 0 0;color:#374151;font-size:13px;line-height:1.6;">
              <strong style="color:#0D5C63;">{coach_name}</strong>
              <span style="color:#6b7280;"> &bull; MJ Realty Coaching</span>
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f0fafa;padding:20px 40px;border-top:1px solid #e5f0f1;">
            <p style="margin:0;color:#9ca3af;font-size:11px;text-align:center;">
              MJ Realty Coaching &bull; Monday new week notification.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    _resend({
        "from":    "MJ Realty Coaching <noreply@creativrealty.com>",
        "to":      [email],
        "subject": f"New week, new goals \u2014 let\u2019s go, {name}!",
        "html":    html,
    }, "monday-new-week")


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


@router.get("/test/sunday")
def test_sunday():
    try:
        send_sunday_reminder_email("Jacques", RECIPIENT, "Martin Gallant")
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/test/monday")
def test_monday():
    try:
        send_monday_new_week_email("Jacques", RECIPIENT, "Martin Gallant")
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/test/welcome-realtor")
def test_welcome_realtor():
    try:
        send_welcome_email("Jacques", RECIPIENT, "Martin Gallant")
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/test/welcome-coach")
def test_welcome_coach():
    try:
        send_coach_welcome_email("Jacques", RECIPIENT)
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("")
def list_feedback():
    return crud.get_all_feedback()


@router.delete("/{feedback_id}")
def remove_feedback(feedback_id: str):
    crud.delete_feedback(feedback_id)
    return {"status": "ok"}
