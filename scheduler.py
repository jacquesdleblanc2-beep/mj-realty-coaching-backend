#!/usr/bin/env python3
# scheduler.py — Runs the weekly coaching pipeline on schedule
# Usage: python scheduler.py
# Runs as a background process; use launchd or a cron wrapper to keep alive.
#
# SCHEDULE:
#   Sunday  8:00 AM → Send reminder emails to all realtors (sheet due tonight)
#   Monday  7:00 AM → Collect scores + create new sheets + send report to Martin

import sys
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scheduler.log"),
    ],
)
log = logging.getLogger(__name__)


def sunday_job():
    log.info("=" * 60)
    log.info("SUNDAY — Sending reminder emails to realtors")
    log.info("=" * 60)
    from pipeline import run_sunday_reminder
    results = run_sunday_reminder(dry_run=False)
    reminded = len(results.get("reminded", []))
    log.info(f"Done. Reminded: {reminded}  Errors: {results.get('errors', {})}")
    if results.get("errors"):
        log.error(f"Errors: {results['errors']}")


def monday_job():
    log.info("=" * 60)
    log.info("MONDAY — Collecting scores + creating new sheets + emailing realtors + Martin")
    log.info("=" * 60)
    from pipeline import run_monday_pipeline
    results = run_monday_pipeline(dry_run=False)
    log.info(f"Done. Sheets: {len(results['sheets'])}  Emails: {len(results['emails'])}")
    if results.get("errors"):
        log.error(f"Errors: {results['errors']}")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="America/Moncton")

    # Every Sunday at 8:00 AM — send reminder emails
    scheduler.add_job(sunday_job, "cron", day_of_week="sun", hour=8, minute=0,
                      id="sunday_reminder", name="Sunday Reminder Emails")

    # Every Monday at 7:00 AM — collect scores + create sheets + send report
    scheduler.add_job(monday_job, "cron", day_of_week="mon", hour=7, minute=0,
                      id="monday_send", name="Monday Sheets + Report")

    log.info("Scheduler started.")
    log.info("  Sunday  8:00 AM → Send reminder emails to all realtors")
    log.info("  Monday  7:00 AM → Collect scores + create new sheets + send report")
    log.info("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
