# config.py — Coaching System Configuration

import os
from dotenv import load_dotenv

load_dotenv()

# ── Martin (coach) ─────────────────────────────────────────────────────────────
MARTIN_EMAIL = os.getenv("MARTIN_EMAIL", "martin@creativrealty.com")
MARTIN_NAME  = "Martin"

# ── Gmail sender ───────────────────────────────────────────────────────────────
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")

# ── Google Drive ───────────────────────────────────────────────────────────────
# Name of the shared Google Drive (Jacques + Martin)
SHARED_DRIVE_NAME  = os.getenv("SHARED_DRIVE_NAME", "")     # leave blank for personal Drive
PERSONAL_FOLDER    = os.getenv("PERSONAL_FOLDER", "MJ Realty")  # parent folder in My Drive
DRIVE_FOLDER_NAME  = "Realty Coaching — Weekly Sheets"           # subfolder inside parent

# ── Realtors registry ──────────────────────────────────────────────────────────
# Managed via the dashboard — stored in realtors.json (no code editing needed).
import json as _json

_REALTORS_PATH = os.path.join(os.path.dirname(__file__), "realtors.json")


def load_realtors() -> list:
    try:
        with open(_REALTORS_PATH) as f:
            return _json.load(f)
    except Exception:
        return []


def save_realtors(realtors: list):
    with open(_REALTORS_PATH, "w") as f:
        _json.dump(realtors, f, indent=2)


# Convenience alias — always reads from file so changes take effect immediately
REALTORS = load_realtors()

# ── Weekly Coaching Checklist ──────────────────────────────────────────────────
# Each item has a category, task description, and point value (total = 100).
COACHING_CHECKLIST = [
    # ── Prospecting (30 pts)
    {"category": "Prospecting",     "task": "Made 10+ prospecting calls",               "points": 8,  "type": "checkbox"},
    {"category": "Prospecting",     "task": "Sent 5+ handwritten notes or personal texts","points": 7,  "type": "checkbox"},
    {"category": "Prospecting",     "task": "Added 3+ new contacts to CRM",              "points": 5,  "type": "checkbox"},
    {"category": "Prospecting",     "task": "Requested 3+ referrals",                    "points": 5,  "type": "checkbox"},
    {"category": "Prospecting",     "task": "Door-knocked or attended 1 community event","points": 5,  "type": "checkbox"},

    # ── Listings & Buyers (25 pts)
    {"category": "Listings/Buyers", "task": "Held or scheduled 1+ listing appointment", "points": 8,  "type": "checkbox"},
    {"category": "Listings/Buyers", "task": "Completed 1+ buyer consultation",           "points": 7,  "type": "checkbox"},
    {"category": "Listings/Buyers", "task": "Reviewed 10+ new MLS listings",             "points": 5,  "type": "checkbox"},
    {"category": "Listings/Buyers", "task": "Sent market update to 5+ clients",          "points": 5,  "type": "checkbox"},

    # ── Follow-Up (20 pts)
    {"category": "Follow-Up",       "task": "Followed up with all active buyers/sellers","points": 8,  "type": "checkbox"},
    {"category": "Follow-Up",       "task": "Touched 10+ leads in CRM (call/text/email)","points": 7,  "type": "checkbox"},
    {"category": "Follow-Up",       "task": "Updated all CRM notes from the week",       "points": 5,  "type": "checkbox"},

    # ── Social & Brand (15 pts)
    {"category": "Social/Brand",    "task": "Posted 3+ times on social media",           "points": 5,  "type": "checkbox"},
    {"category": "Social/Brand",    "task": "Shared 1+ educational real estate content", "points": 5,  "type": "checkbox"},
    {"category": "Social/Brand",    "task": "Requested 1+ Google/Zillow review",         "points": 5,  "type": "checkbox"},

    # ── Education & Growth (10 pts)
    {"category": "Education",       "task": "Spent 30+ min on training/education",       "points": 5,  "type": "checkbox"},
    {"category": "Education",       "task": "Reviewed last week's coaching notes",       "points": 5,  "type": "checkbox"},
]

# ── Activity Log columns ────────────────────────────────────────────────────────
# Columns mirror the Weekly Strategy categories so daily tracking aligns with weekly goals.
ACTIVITY_LOG_COLUMNS = [
    "Day",
    "Prospecting",
    "Listings / Buyers",
    "Follow-Up",
    "Social / Brand",
    "Education",
    "Notes / Wins",
]

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ── Scoring thresholds ─────────────────────────────────────────────────────────
SCORE_THRESHOLDS = {
    "Excellent":   (90, 100, "#1a5c2a"),   # green
    "Strong":      (75,  89, "#2a4a1a"),   # dark green
    "On Track":    (60,  74, "#4a4a00"),   # olive
    "Needs Work":  (40,  59, "#7a3a00"),   # orange
    "Off Track":   (0,   39, "#7a1a1a"),   # red
}

def init_realtor_tasks() -> list:
    """Return a fresh copy of all standard tasks with enabled=True, is_custom=False."""
    import copy
    return [
        {**copy.deepcopy(t), "enabled": True, "is_custom": False}
        for t in COACHING_CHECKLIST
    ]


def score_label(score: int) -> tuple[str, str]:
    """Return (label, hex_color) for a given score 0–100."""
    for label, (lo, hi, color) in SCORE_THRESHOLDS.items():
        if lo <= score <= hi:
            return label, color
    return "Off Track", "#7a1a1a"
