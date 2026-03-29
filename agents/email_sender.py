# agents/email_sender.py — Sunday sheet emails + Monday report emails

import os
import sys
import base64
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GMAIL_SENDER, score_label

# Reuse the single shared OAuth token (covers Sheets + Drive + Gmail)
CREDS_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials")
TOKEN_PATH = os.path.join(CREDS_DIR, "google_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
]


def _get_gmail():
    """Build Gmail service using the shared OAuth token."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    OAUTH_PATH = os.path.join(CREDS_DIR, "oauth_credentials.json")
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(OAUTH_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _send(gmail, to: str, subject: str, html_body: str, dry_run=False) -> dict:
    if dry_run:
        return {"status": "dry_run", "to": to, "subject": subject}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = to
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = gmail.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return {"status": "sent", "to": to, "subject": subject, "message_id": sent["id"]}


# ── Welcome email when realtor is first added ─────────────────────────────────

def send_welcome_email(realtor: dict, folder_url: str, dry_run=False) -> dict:
    """Send a one-time welcome email to a newly added realtor with their Drive folder link."""
    gmail   = _get_gmail()
    subject = f"Welcome to MJ Realty Coaching, {realtor['name']}!"
    html    = _welcome_email_html(realtor, folder_url)
    result  = _send(gmail, realtor["email"], subject, html, dry_run=dry_run)
    result["realtor_name"] = realtor["name"]
    result["timestamp"]    = datetime.now().isoformat()
    print(f"  {'[DRY RUN]' if dry_run else '[SENT]'} Welcome email → {realtor['name']} <{realtor['email']}>")
    return result


def _welcome_email_html(realtor: dict, folder_url: str) -> str:
    focus = realtor.get("coaching_focus", "General coaching")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f0f1f4;color:#2c3e50;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">

    <div style="background:linear-gradient(135deg,#1a2f4b,#334f74);
                border-radius:14px;padding:28px;margin-bottom:24px;text-align:center;">
      <div style="font-size:2.2em;margin-bottom:8px;">🏠</div>
      <h1 style="color:white;margin:0;font-size:1.6em;letter-spacing:0.5px;">
        Welcome to MJ Realty Coaching
      </h1>
      <p style="color:#9daebe;margin:6px 0 0;font-size:0.95em;">Your coaching journey starts here</p>
    </div>

    <div style="background:white;border:1px solid #d0dae3;border-radius:12px;padding:24px;">
      <p style="color:#1a2f4b;font-size:1.05em;margin-top:0;">
        Hi <strong>{realtor['name']}</strong> 👋
      </p>
      <p style="color:#687988;">
        Martin has set you up in the MJ Realty Coaching System. Every Monday you'll
        receive a new weekly accountability sheet, and your progress is tracked over time
        so you can see yourself improving.
      </p>
      <p style="color:#687988;">
        Your coaching focus: <strong style="color:#1a2f4b;">{focus}</strong>
      </p>

      <div style="background:#eaf2f9;border-left:4px solid #2980b9;
                  border-radius:0 8px 8px 0;padding:16px 18px;margin:20px 0;">
        <p style="color:#1a2f4b;margin:0 0 8px;font-weight:700;">📁 Your personal coaching folder</p>
        <p style="color:#687988;margin:0 0 14px;font-size:0.9em;">
          All your weekly sheets live here — bookmark this link so you always have access,
          even before your Monday email arrives.
        </p>
        <a href="{folder_url}"
           style="display:inline-block;background:#2980b9;color:white;padding:10px 24px;
                  border-radius:8px;text-decoration:none;font-weight:700;font-size:0.95em;">
          Open My Coaching Folder ↗
        </a>
      </div>

      <p style="color:#687988;font-size:0.9em;">
        <strong>How it works:</strong> Each Monday morning you'll get a fresh sheet for the week.
        Fill in your activity log daily, complete the checklist by Sunday, and Martin reviews
        everything and sends a coaching report on Monday.
      </p>

      <p style="color:#9daebe;font-size:0.82em;margin-bottom:0;">
        Aim for <strong style="color:#27ae60;">90%+</strong> each week — let's get to work! 💪
      </p>
    </div>

    <p style="color:#9daebe;font-size:0.75em;text-align:center;margin-top:20px;">
      MJ Realty Coaching System &nbsp;·&nbsp; Questions? Reply to this email.
    </p>
  </div>
</body>
</html>"""


# ── Sunday: reminder emails (sheet due tonight) ───────────────────────────────

def send_sunday_reminder(sheet_entries: list, dry_run=False) -> list:
    """
    Send a warm reminder to each realtor that their sheet is due tonight.
    sheet_entries: list of {realtor_name, realtor_email, sheet_url, week_label}
    """
    gmail = _get_gmail()
    log   = []

    for entry in sheet_entries:
        first_name = entry["realtor_name"].split()[0]
        subject    = "⏰ Reminder: Your coaching sheet is due tonight"
        html       = _sunday_reminder_html(entry, first_name)
        result     = _send(gmail, entry["realtor_email"], subject, html, dry_run=dry_run)
        result["realtor_name"] = entry["realtor_name"]
        result["timestamp"]    = datetime.now().isoformat()
        log.append(result)
        print(f"  {'[DRY RUN]' if dry_run else '[SENT]'} Sunday reminder → {entry['realtor_name']} <{entry['realtor_email']}>")

    return log


def _sunday_reminder_html(entry: dict, first_name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f0f1f4;color:#2c3e50;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">

    <div style="background:linear-gradient(135deg,#1a2f4b,#334f74);
                border-radius:14px;padding:28px;margin-bottom:24px;text-align:center;">
      <div style="font-size:2.2em;margin-bottom:8px;">⏰</div>
      <h1 style="color:white;margin:0;font-size:1.6em;letter-spacing:0.5px;">
        Don't forget — sheet due tonight!
      </h1>
      <p style="color:#9daebe;margin:6px 0 0;font-size:0.92em;">{entry['week_label']}</p>
    </div>

    <div style="background:white;border:1px solid #d0dae3;border-radius:12px;padding:24px;">
      <p style="color:#1a2f4b;font-size:1.05em;margin-top:0;">
        Hey <strong>{first_name}</strong> 👋
      </p>
      <p style="color:#687988;">
        Just a quick reminder — your weekly coaching sheet needs to be completed
        <strong style="color:#1a2f4b;">before midnight tonight.</strong>
        You've put in the work all week. Take 5 minutes to lock it in.
      </p>

      <div style="text-align:center;margin:28px 0;">
        <a href="{entry['sheet_url']}"
           style="display:inline-block;background:linear-gradient(135deg,#1a2f4b,#2980b9);
                  color:white;padding:14px 36px;border-radius:10px;text-decoration:none;
                  font-weight:700;font-size:1.05em;letter-spacing:0.3px;">
          ✅ Open My Sheet &amp; Complete Checklist
        </a>
      </div>

      <div style="background:#f9fafb;border:1px solid #d0dae3;border-radius:8px;
                  padding:14px 18px;margin:20px 0;">
        <p style="color:#1a2f4b;margin:0 0 6px;font-weight:700;font-size:0.9em;">
          📋 Quick checklist before you submit:
        </p>
        <ul style="color:#687988;margin:0;padding-left:20px;line-height:1.8;font-size:0.92em;">
          <li>Activity log filled in for each day</li>
          <li>Weekly Strategy tab completed</li>
          <li>Leave a note for Martin if anything stood out</li>
        </ul>
      </div>

      <p style="color:#687988;font-size:0.92em;">
        Every rep counts. Every week you complete this is a week closer to your goals.
        Let's finish strong 💪
      </p>

      <p style="color:#9daebe;font-size:0.82em;margin-bottom:0;margin-top:20px;">
        — Martin &amp; the MJ Realty Coaching Team
      </p>
    </div>

    <p style="color:#9daebe;font-size:0.75em;text-align:center;margin-top:20px;">
      MJ Realty Coaching System &nbsp;·&nbsp; Sent every Sunday morning
    </p>
  </div>
</body>
</html>"""


# ── Sunday: send new sheet links (legacy — kept for reference) ─────────────────

def send_sunday_emails(sheet_results: list[dict], dry_run=False) -> list[dict]:
    """
    sheet_results: list of {realtor, sheet_info} dicts from create_weekly_sheet.
    Sends each realtor an email with their sheet link.
    """
    gmail = _get_gmail()
    log   = []


def send_sunday_emails(sheet_results: list[dict], dry_run=False) -> list[dict]:
    """
    sheet_results: list of {realtor, sheet_info} dicts from create_weekly_sheet.
    Sends each realtor an email with their sheet link.
    """
    gmail = _get_gmail()
    log   = []

    for item in sheet_results:
        realtor    = item["realtor"]
        sheet_info = item["sheet_info"]
        subject    = f"🏠 Your Coaching Sheet — {sheet_info['week_label']}"
        html       = _sunday_email_html(realtor, sheet_info)
        result     = _send(gmail, realtor["email"], subject, html, dry_run=dry_run)
        result["realtor_name"] = realtor["name"]
        result["timestamp"]    = datetime.now().isoformat()
        log.append(result)
        print(f"  {'[DRY RUN]' if dry_run else '[SENT]'} Sunday email → {realtor['name']} <{realtor['email']}>")

    return log


def _sunday_email_html(realtor: dict, sheet_info: dict) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#0f0f1a;color:#ddd;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">

    <div style="background:linear-gradient(135deg,#0f0f1a,#1a1a35);
                border:1px solid #2a2a4a;border-radius:14px;
                padding:28px;margin-bottom:24px;text-align:center;">
      <div style="font-size:2.2em;margin-bottom:8px;">🏠</div>
      <h1 style="color:white;margin:0;font-size:1.6em;">MJ Realty Coaching</h1>
      <p style="color:#7a8aaa;margin:6px 0 0;font-size:0.95em;">Weekly Accountability Sheet</p>
    </div>

    <div style="background:#1e1e2e;border:1px solid #2a2a4a;border-radius:12px;padding:24px;">
      <p style="color:white;font-size:1.05em;margin-top:0;">
        Hi <strong style="color:#4da6ff;">{realtor['name']}</strong> 👋
      </p>
      <p style="color:#aab;">
        Your weekly coaching sheet is ready for <strong style="color:white;">
        {sheet_info['week_label']}</strong>.
      </p>
      <p style="color:#aab;">
        This week's coaching focus: <strong style="color:#4dcc7a;">
        {realtor['coaching_focus']}</strong>
      </p>

      <div style="background:#0d0d1a;border-radius:10px;padding:16px;margin:20px 0;">
        <p style="color:#7a8aaa;margin:0 0 6px;font-size:0.85em;text-transform:uppercase;letter-spacing:1px;">
          YOUR SHEET
        </p>
        <a href="{sheet_info['url']}"
           style="color:#4da6ff;font-size:1.1em;word-break:break-all;">{sheet_info['url']}</a>
      </div>

      <div style="border-left:3px solid #4da6ff;padding-left:16px;margin:20px 0;">
        <p style="color:white;margin:0 0 8px;font-weight:700;">📋 What to do:</p>
        <ol style="color:#aab;margin:0;padding-left:20px;line-height:1.8;">
          <li>Open your sheet using the link above</li>
          <li>Each day, fill in your <strong>Activity Log</strong></li>
          <li>At the end of the week, check off your <strong>Weekly Checklist</strong></li>
          <li>Complete the <strong>Goals &amp; Reflection</strong> tab</li>
          <li>Leave a note for Martin if needed</li>
        </ol>
      </div>

      <p style="color:#666;font-size:0.85em;margin-bottom:0;">
        Martin will review your sheet on Monday and send a coaching report.
        Aim for <strong style="color:#4dcc7a;">90%+</strong> this week! 💪
      </p>
    </div>

    <p style="color:#444;font-size:0.78em;text-align:center;margin-top:20px;">
      MJ Realty Coaching System &nbsp;·&nbsp; Sent every Sunday
    </p>
  </div>
</body>
</html>
"""


# ── Monday: send each realtor their new sheet + last week's score ─────────────

def send_monday_emails(sheet_results: list[dict], report: dict, dry_run=False) -> list[dict]:
    """
    Monday morning: email each realtor their new week's sheet + last week's score.
    sheet_results: list of {realtor, sheet_info}
    report: last week's report dict from build_monday_report
    """
    gmail = _get_gmail()
    log   = []

    # Build a lookup of last week's scores by realtor name
    scores = {e["realtor_name"]: e for e in report.get("entries", [])}

    for item in sheet_results:
        realtor    = item["realtor"]
        sheet_info = item["sheet_info"]
        last_week  = scores.get(realtor["name"], {})
        subject    = f"🏠 Your New Coaching Sheet — {sheet_info['week_label']}"
        html       = _monday_realtor_email_html(realtor, sheet_info, last_week, report.get("week_label", ""))
        result     = _send(gmail, realtor["email"], subject, html, dry_run=dry_run)
        result["realtor_name"] = realtor["name"]
        result["timestamp"]    = datetime.now().isoformat()
        log.append(result)
        print(f"  {'[DRY RUN]' if dry_run else '[SENT]'} Monday email → {realtor['name']} <{realtor['email']}>")

    return log


def _monday_realtor_email_html(realtor: dict, sheet_info: dict, last_week: dict, prev_week_label: str) -> str:
    from config import score_label

    # Last week score section
    if last_week.get("uploaded"):
        pct          = last_week.get("percentage", 0)
        label, color = score_label(pct)
        last_week_html = f"""
        <div style="background:#f9fafb;border:1px solid #d0dae3;border-radius:10px;
                    padding:16px;margin:20px 0;">
          <p style="color:#687988;margin:0 0 8px;font-size:0.82em;text-transform:uppercase;
                    letter-spacing:0.5px;">Last Week — {prev_week_label}</p>
          <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
            <span style="background:{color};color:white;padding:6px 18px;border-radius:20px;
                         font-weight:700;font-size:1.1em;">{pct}% — {label}</span>
            <span style="color:#1a2f4b;font-size:0.95em;">
              {last_week.get('score', 0)} / {last_week.get('total_possible', 100)} pts
            </span>
          </div>
        </div>"""
    elif prev_week_label:
        last_week_html = f"""
        <div style="background:#fff5f5;border:1px solid #f5c0c0;border-radius:10px;
                    padding:12px 16px;margin:20px 0;">
          <p style="color:#c0392b;margin:0;font-size:0.9em;">
            ⚠️ No submission found for {prev_week_label}. Let's make this week count!
          </p>
        </div>"""
    else:
        last_week_html = ""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f0f1f4;color:#2c3e50;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">

    <div style="background:linear-gradient(135deg,#1a2f4b,#334f74);
                border-radius:14px;padding:28px;margin-bottom:24px;text-align:center;">
      <div style="font-size:2em;margin-bottom:8px;">🏠</div>
      <h1 style="color:white;margin:0;font-size:1.6em;letter-spacing:0.5px;">
        MJ Realty Coaching
      </h1>
      <p style="color:#9daebe;margin:6px 0 0;font-size:0.9em;">Weekly Accountability Sheet</p>
    </div>

    <div style="background:white;border:1px solid #d0dae3;border-radius:12px;padding:24px;">
      <p style="color:#1a2f4b;font-size:1.05em;margin-top:0;">
        Good morning, <strong>{realtor['name']}</strong> 👋
      </p>
      <p style="color:#687988;">
        Your coaching sheet for <strong style="color:#1a2f4b;">
        {sheet_info['week_label']}</strong> is ready.
      </p>

      {last_week_html}

      <div style="background:#eaf2f9;border-left:4px solid #2980b9;
                  border-radius:0 8px 8px 0;padding:14px 18px;margin:20px 0;">
        <p style="color:#1a2f4b;margin:0 0 8px;font-weight:700;">📋 This week's sheet:</p>
        <a href="{sheet_info['url']}" style="color:#2980b9;font-size:0.95em;word-break:break-all;">
          {sheet_info['url']}
        </a>
      </div>

      <p style="color:#1a2f4b;font-weight:700;margin-bottom:8px;">How to use it:</p>
      <ol style="color:#687988;margin:0;padding-left:20px;line-height:1.9;">
        <li>Check the <strong>Overview tab</strong> — see Martin's goals for you this week</li>
        <li>Add your own <strong>personal goals</strong> for the week</li>
        <li>Each day, fill in the <strong>Activity Log</strong> (2 minutes)</li>
        <li>By Sunday, complete your <strong>Checklist</strong></li>
        <li>Your score is calculated automatically</li>
      </ol>

      <p style="color:#9daebe;font-size:0.82em;margin-top:20px;margin-bottom:0;">
        Martin will review your results. Aim for <strong style="color:#27ae60;">90%+</strong>
        — you've got this! 💪
      </p>
    </div>

    <p style="color:#9daebe;font-size:0.75em;text-align:center;margin-top:20px;">
      MJ Realty Coaching System &nbsp;·&nbsp; Sent every Monday morning
    </p>
  </div>
</body>
</html>
"""


# ── Monday: send Martin's report ──────────────────────────────────────────────

def send_monday_report(report: dict, martin_email: str, dry_run=False) -> dict:
    """Send the weekly summary report to Martin."""
    gmail   = _get_gmail()
    subject = f"📊 Weekly Coaching Report — {report['week_label']}"
    html    = _monday_report_html(report)
    result  = _send(gmail, martin_email, subject, html, dry_run=dry_run)
    result["timestamp"] = datetime.now().isoformat()
    print(f"  {'[DRY RUN]' if dry_run else '[SENT]'} Monday report → Martin <{martin_email}>")
    return result


def _monday_report_html(report: dict) -> str:
    rows_html = ""
    for entry in report["entries"]:
        label, color = score_label(entry["percentage"])
        uploaded_sym = "✅" if entry["uploaded"] else "❌"
        rows_html += f"""
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid #2a2a4a;color:white;font-weight:600;">
            {entry['realtor_name']}
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #2a2a4a;text-align:center;font-size:1.2em;">
            {uploaded_sym}
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #2a2a4a;text-align:center;">
            <span style="background:{color};color:white;padding:4px 12px;border-radius:20px;
                         font-weight:700;font-size:0.9em;">{entry['percentage']}%</span>
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #2a2a4a;text-align:center;">
            <span style="background:{color};color:white;padding:4px 10px;border-radius:12px;
                         font-size:0.82em;">{label}</span>
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #2a2a4a;color:#4da6ff;
                     font-size:0.85em;">
            <a href="{entry['sheet_url']}" style="color:#4da6ff;">View Sheet</a>
          </td>
        </tr>"""

    # Detailed breakdown per realtor
    details_html = ""
    for entry in report["entries"]:
        if not entry["uploaded"]:
            details_html += f"""
            <div style="background:#1e1e2e;border:1px solid #3a0d0d;border-radius:10px;
                        padding:16px;margin-bottom:16px;">
              <h3 style="color:#ff5555;margin:0 0 8px;">{entry['realtor_name']} — Did not upload</h3>
            </div>"""
            continue

        label, color = score_label(entry["percentage"])
        completed_html = "".join(
            f'<li style="color:#4dcc7a;">✓ {t}</li>' for t in entry["completed"]
        )
        incomplete_html = "".join(
            f'<li style="color:#ff7777;">✗ {t}</li>' for t in entry["incomplete"]
        )

        # Activity totals
        act_rows = ""
        for k, v in entry.get("activity_totals", {}).items():
            act_rows += f"""
            <tr>
              <td style="padding:4px 12px;color:#aab;font-size:0.88em;">{k}</td>
              <td style="padding:4px 12px;color:white;font-weight:700;text-align:right;">{v}</td>
            </tr>"""

        note_section = ""
        if entry.get("note_to_martin"):
            note_section = f"""
            <div style="background:#0d2a44;border-left:3px solid #4da6ff;
                        padding:12px 16px;border-radius:0 8px 8px 0;margin-top:12px;">
              <p style="color:#7a8aaa;margin:0 0 4px;font-size:0.8em;text-transform:uppercase;">
                Note to Martin
              </p>
              <p style="color:#ddd;margin:0;font-style:italic;">"{entry['note_to_martin']}"</p>
            </div>"""

        details_html += f"""
        <div style="background:#1e1e2e;border:1px solid #2a2a4a;border-radius:10px;
                    padding:20px;margin-bottom:20px;">
          <div style="display:flex;justify-content:space-between;align-items:center;
                      flex-wrap:wrap;gap:8px;margin-bottom:16px;">
            <h3 style="color:white;margin:0;font-size:1.1em;">{entry['realtor_name']}</h3>
            <span style="background:{color};color:white;padding:6px 16px;border-radius:20px;
                         font-weight:700;">{entry['percentage']}% — {label}</span>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            <div>
              <p style="color:#7a8aaa;margin:0 0 6px;font-size:0.8em;text-transform:uppercase;">
                Completed ({len(entry['completed'])})
              </p>
              <ul style="margin:0;padding-left:16px;line-height:1.7;">{completed_html}</ul>
            </div>
            <div>
              <p style="color:#7a8aaa;margin:0 0 6px;font-size:0.8em;text-transform:uppercase;">
                Not Completed ({len(entry['incomplete'])})
              </p>
              <ul style="margin:0;padding-left:16px;line-height:1.7;">{incomplete_html}</ul>
            </div>
          </div>

          {'<table style="margin-top:16px;width:100%;">' + act_rows + '</table>' if act_rows else ''}
          {note_section}
        </div>"""

    submitted    = sum(1 for e in report["entries"] if e["uploaded"])
    avg_score    = (sum(e["percentage"] for e in report["entries"] if e["uploaded"]) // max(submitted, 1))
    avg_label, avg_color = score_label(avg_score)

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#0f0f1a;color:#ddd;margin:0;padding:0;">
  <div style="max-width:720px;margin:0 auto;padding:32px 24px;">

    <div style="background:linear-gradient(135deg,#0f0f1a,#1a1a35);
                border:1px solid #2a2a4a;border-radius:14px;
                padding:28px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <div style="font-size:2em;">📊</div>
        <div>
          <h1 style="color:white;margin:0;font-size:1.5em;">Weekly Coaching Report</h1>
          <p style="color:#7a8aaa;margin:4px 0 0;">{report['week_label']}</p>
        </div>
        <div style="margin-left:auto;text-align:right;">
          <div style="background:{avg_color};color:white;padding:8px 20px;border-radius:20px;
                      font-weight:700;font-size:1.1em;">Avg: {avg_score}%</div>
          <div style="color:#7a8aaa;font-size:0.82em;margin-top:4px;">{avg_label}</div>
        </div>
      </div>
    </div>

    <!-- Summary table -->
    <div style="background:#1e1e2e;border:1px solid #2a2a4a;border-radius:12px;
                overflow:hidden;margin-bottom:24px;">
      <div style="padding:16px 20px;border-bottom:1px solid #2a2a4a;">
        <h2 style="color:white;margin:0;font-size:1.1em;">
          Summary &nbsp;·&nbsp;
          <span style="color:#4dcc7a;">{submitted}/{len(report['entries'])}</span>
          submitted
        </h2>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#16162a;">
            <th style="padding:10px 16px;text-align:left;color:#7a8aaa;font-size:0.85em;
                       text-transform:uppercase;letter-spacing:0.5px;">Realtor</th>
            <th style="padding:10px 16px;text-align:center;color:#7a8aaa;font-size:0.85em;
                       text-transform:uppercase;">Uploaded</th>
            <th style="padding:10px 16px;text-align:center;color:#7a8aaa;font-size:0.85em;
                       text-transform:uppercase;">Score</th>
            <th style="padding:10px 16px;text-align:center;color:#7a8aaa;font-size:0.85em;
                       text-transform:uppercase;">Rating</th>
            <th style="padding:10px 16px;color:#7a8aaa;font-size:0.85em;
                       text-transform:uppercase;">Sheet</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>

    <!-- Detailed breakdown -->
    <h2 style="color:white;margin:0 0 16px;font-size:1.1em;">Detailed Breakdown</h2>
    {details_html}

    <p style="color:#444;font-size:0.78em;text-align:center;margin-top:24px;">
      MJ Realty Coaching System &nbsp;·&nbsp; Automated Monday Report
    </p>
  </div>
</body>
</html>
"""
