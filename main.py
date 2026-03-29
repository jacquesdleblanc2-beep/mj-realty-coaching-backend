#!/usr/bin/env python3
# main.py — CLI for MJ Realty Coaching System
# Usage:
#   python main.py --sunday          # Send Sunday reminder emails to realtors
#   python main.py --monday          # Collect scores + create new sheets + email everyone
#   python main.py --sunday --dryrun # Preview without sending
#   python main.py --monday --dryrun # Preview without sending

import argparse
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="MJ Realty Coaching System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --sunday           # Sunday pipeline (live): send reminder emails
  python main.py --monday           # Monday pipeline (live): collect scores + create sheets
  python main.py --sunday --dryrun  # Dry run: no emails sent
  python main.py --monday --dryrun  # Dry run: report printed only
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sunday", action="store_true",
                       help="Run Sunday pipeline (send reminder emails to realtors)")
    group.add_argument("--monday", action="store_true",
                       help="Run Monday pipeline (collect scores + create new sheets + email everyone)")
    parser.add_argument("--dryrun", action="store_true", help="Preview only — do not send emails")
    parser.add_argument("--week",   type=str, default=None,
                        help="Override week label (for Monday report, e.g. 'Week of Apr 7 – Apr 13, 2025')")
    args = parser.parse_args()

    print("\n🏠  MJ Realty — Coaching System")
    print("=" * 55)
    mode = "DRY RUN" if args.dryrun else "LIVE"
    print(f"Mode: {mode}")

    if args.sunday:
        print("Pipeline: SUNDAY — send reminder emails to realtors\n")
        from pipeline import run_sunday_reminder

        def _cb(msg):
            print(f"  {msg}")

        results = run_sunday_reminder(dry_run=args.dryrun, progress_cb=_cb)
        print(f"\n✅ Done.")
        reminded = results.get("reminded", [])
        print(f"   Reminders sent: {len(reminded)}")
        for r in reminded:
            name   = r.get("realtor_name", r.get("to", "?"))
            status = r.get("status", "?")
            print(f"   ✉️  {name:<25} [{status}]")
        if results.get("errors"):
            print(f"   Errors: {results['errors']}")
            sys.exit(1)

    elif args.monday:
        print("Pipeline: MONDAY — collect scores + create sheets + email everyone\n")
        from pipeline import run_monday_pipeline

        def _cb(msg):
            print(f"  {msg}")

        results = run_monday_pipeline(dry_run=args.dryrun, progress_cb=_cb)
        report  = results.get("report", {})
        print(f"\n✅ Done.")
        print(f"   New week:  {results['week_label']}")
        print(f"   Sheets:    {len(results['sheets'])}")
        print(f"   Emails:    {len(results['emails'])}")
        if report:
            print(f"   Last week: {report.get('week_label','')}")
            print(f"   Submitted: {report.get('submitted', 0)}/{report.get('total_realtors', 0)}")
            for entry in report.get("entries", []):
                sym = "✅" if entry["uploaded"] else "❌"
                print(f"   {sym} {entry['realtor_name']:<25} {entry['percentage']}%")
        if results.get("errors"):
            print(f"   Errors: {results['errors']}")
            sys.exit(1)


if __name__ == "__main__":
    main()
