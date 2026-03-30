# pipeline.py — Weekly pipeline: Monday score collection + sheet creation, Sunday reminders
#
# WEEKLY FLOW:
#   Monday 7:00 AM  — run_monday_pipeline()
#     1. Read last week's sheets → collect scores → save to Supabase
#     2. Build Martin's coaching report from those scores
#     3. Email Martin the report
#     4. Create new week's Google Sheets for each realtor
#     5. Email each realtor: new sheet link + last week's score summary
#     6. Log all sheet creation as event="monday_send"
#
#   Sunday 8:00 AM  — run_sunday_reminder()
#     1. Find each realtor's current-week sheet from send_log (Supabase)
#     2. Send reminder emails — "your sheet is due tonight"
#     3. Log as event="sunday_reminder"
#     No score collection. No sheet creation. Reminders only.

from datetime import datetime, timedelta

import crud
from config import MARTIN_EMAIL
from agents.sheets_manager import create_weekly_sheet
from agents.email_sender   import send_monday_emails, send_monday_report, send_sunday_reminder
from agents.reporter       import build_monday_report


def _week_label() -> str:
    today  = datetime.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return f"Week of {monday.strftime('%b %-d')} – {sunday.strftime('%b %-d, %Y')}"


def _prev_week_label() -> str:
    """Return the Mon–Sun week label for the week that just ended."""
    today        = datetime.today()
    this_monday  = today - timedelta(days=today.weekday())
    prev_monday  = this_monday - timedelta(weeks=1)
    prev_sunday  = prev_monday + timedelta(days=6)
    return f"Week of {prev_monday.strftime('%b %-d')} – {prev_sunday.strftime('%b %-d, %Y')}"


# ── SUNDAY: send reminder emails ──────────────────────────────────────────────

def run_sunday_reminder(dry_run=False, progress_cb=None) -> dict:
    """
    Sunday 8:00 AM job.
    Finds each realtor's current-week sheet from Supabase send_log and sends
    a reminder email to complete their checklist before midnight.
    No score collection. No sheet creation.
    """
    def _cb(msg):
        if progress_cb: progress_cb(msg)
        else: print(msg)

    week_label = _week_label()
    results    = {"week_label": week_label, "reminded": [], "errors": {}}

    _cb(f"📨 Sunday reminders for: {week_label}")

    log_entries = crud.get_log_by_week_event(week_label, "monday_send")

    if not log_entries:
        _cb("  ⚠️  No sheets found for this week — run the Monday pipeline first.")
        return results

    sheet_entries = [
        {
            "realtor_name":  e["details"]["realtor_name"],
            "realtor_email": e["details"]["realtor_email"],
            "sheet_url":     e["details"].get("sheet_url", ""),
            "week_label":    week_label,
        }
        for e in log_entries
        if e.get("details", {}).get("realtor_email") and e.get("details", {}).get("sheet_url")
    ]

    _cb(f"  {len(sheet_entries)} realtors to remind…")

    try:
        email_log = send_sunday_reminder(sheet_entries, dry_run=dry_run)
        for r in email_log:
            results["reminded"].append(r)
            name = r.get("realtor_name", r.get("to", ""))
            _cb(f"    {'[DRY RUN]' if dry_run else '✅'} Reminded {name}")
    except Exception as e:
        results["errors"]["reminder_emails"] = str(e)
        _cb(f"  ❌ Reminder email error: {e}")

    crud.append_log("sunday_reminder", week_label=week_label, dry_run=dry_run, details={
        "reminded": [e.get("realtor_name", "") for e in results["reminded"]],
    })

    return results


# ── MONDAY: collect scores + build report + create new sheets + email everyone ─

def run_monday_pipeline(dry_run=True, progress_cb=None) -> dict:
    """
    Monday 7:00 AM job — exact order:
    1. Read last week's sheets → collect scores → save to Supabase
    2. Build Martin's report from those scores
    3. Email Martin the report
    4. Create new week's Google Sheets for each realtor
    5. Email each realtor: new sheet link + last week's score summary
    6. Log sheet creation as event="monday_send"
    """
    def _cb(msg):
        if progress_cb: progress_cb(msg)
        else: print(msg)

    week_label      = _week_label()
    prev_week_label = _prev_week_label()
    results         = {"week_label": week_label, "sheets": [], "emails": [], "errors": {}}

    realtors = crud.get_all_realtors()
    _cb(f"📋 Monday pipeline — new week: {week_label}")
    _cb(f"👥 {len(realtors)} realtors\n")

    # ── Step 1-3: Collect last week's scores + build report ───────────────────
    _cb(f"📊 Step 1 — Reading last week's sheets: {prev_week_label}")
    report = build_monday_report(prev_week_label)
    _cb(f"  {report['submitted']}/{report['total_realtors']} submitted last week")
    results["report"] = report

    # ── Step 4: Email Martin ──────────────────────────────────────────────────
    _cb(f"\n📧 Step 2 — Emailing Martin ({'dry run' if dry_run else 'live'})…")
    try:
        martin_email = send_monday_report(report, MARTIN_EMAIL, dry_run=dry_run)
        results["martin_email"] = martin_email
    except Exception as e:
        results["errors"]["martin_email"] = str(e)
        _cb(f"  ❌ Martin email error: {e}")

    # ── Step 5: Create new sheets ─────────────────────────────────────────────
    _cb(f"\n📄 Step 3 — Creating new sheets for: {week_label}")
    sheet_results = []
    for realtor in realtors:
        _cb(f"  Creating sheet for {realtor['name']}…")
        try:
            sheet_info = create_weekly_sheet(realtor)
            sheet_results.append({"realtor": realtor, "sheet_info": sheet_info})
            results["sheets"].append({
                "realtor_name":   realtor["name"],
                "spreadsheet_id": sheet_info["spreadsheet_id"],
                "url":            sheet_info["url"],
                "reused":         sheet_info.get("reused", False),
            })
            action = "reused" if sheet_info.get("reused") else "created"
            _cb(f"    ✅ Sheet {action}: {sheet_info['url']}")
        except Exception as e:
            results["errors"][realtor["name"]] = str(e)
            _cb(f"    ❌ {realtor['name']}: {e}")

    # ── Step 6: Email realtors ────────────────────────────────────────────────
    _cb(f"\n📧 Step 4 — Emailing realtors ({'dry run' if dry_run else 'live'})…")
    try:
        email_log = send_monday_emails(sheet_results, report, dry_run=dry_run)
        results["emails"] = email_log
    except Exception as e:
        results["errors"]["realtor_emails"] = str(e)
        _cb(f"  ❌ Realtor email error: {e}")

    # ── Step 7: Log ───────────────────────────────────────────────────────────
    for sr in sheet_results:
        crud.append_log("monday_send", week_label=week_label, dry_run=dry_run, details={
            "realtor_name":   sr["realtor"]["name"],
            "realtor_email":  sr["realtor"]["email"],
            "spreadsheet_id": sr["sheet_info"]["spreadsheet_id"],
            "sheet_url":      sr["sheet_info"]["url"],
        })
    crud.append_log("monday_report", week_label=prev_week_label, dry_run=dry_run, details={
        "to":        MARTIN_EMAIL,
        "submitted": report["submitted"],
        "total":     report["total_realtors"],
        "status":    results.get("martin_email", {}).get("status"),
    })

    _cb(f"\n✅ Monday pipeline complete.")
    _cb(f"   Sheets:  {len(results['sheets'])}")
    _cb(f"   Emails:  {len(results['emails'])}")
    if results["errors"]:
        _cb(f"   Errors:  {results['errors']}")

    return results
