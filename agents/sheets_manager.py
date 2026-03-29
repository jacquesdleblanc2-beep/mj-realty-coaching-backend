# agents/sheets_manager.py — Google Sheets + Drive integration

import os
import sys
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    DRIVE_FOLDER_NAME, SHARED_DRIVE_NAME, PERSONAL_FOLDER,
    COACHING_CHECKLIST, ACTIVITY_LOG_COLUMNS, DAYS_OF_WEEK
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDS_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials")
TOKEN_PATH = os.path.join(CREDS_DIR, "google_token.json")
OAUTH_PATH = os.path.join(CREDS_DIR, "oauth_credentials.json")

# ── Premium light color palette ───────────────────────────────────────────────
# Primary brand
C_NAVY        = {"red": 0.102, "green": 0.184, "blue": 0.294}   # #1A2F4B
C_NAVY_MED    = {"red": 0.200, "green": 0.322, "blue": 0.455}   # #334F74
C_NAVY_LIGHT  = {"red": 0.886, "green": 0.910, "blue": 0.937}   # #E2E8EF very light navy

# Accent
C_GOLD        = {"red": 0.953, "green": 0.612, "blue": 0.071}   # #F39C12
C_GOLD_LIGHT  = {"red": 1.000, "green": 0.961, "blue": 0.863}   # #FFF5DC

# Blue (Martin)
C_BLUE        = {"red": 0.165, "green": 0.502, "blue": 0.733}   # #2980B9
C_BLUE_LIGHT  = {"red": 0.918, "green": 0.949, "blue": 0.976}   # #EAF2F9

# Green (success / personal)
C_GREEN       = {"red": 0.153, "green": 0.682, "blue": 0.376}   # #27AE60
C_GREEN_LIGHT = {"red": 0.882, "green": 0.961, "blue": 0.910}   # #E1F5E8

# Neutrals
C_WHITE       = {"red": 1.000, "green": 1.000, "blue": 1.000}
C_OFF_WHITE   = {"red": 0.976, "green": 0.980, "blue": 0.988}   # #F9FAFB
C_GRAY_LIGHT  = {"red": 0.941, "green": 0.945, "blue": 0.953}   # #F0F1F4
C_BORDER      = {"red": 0.816, "green": 0.855, "blue": 0.890}   # #D0DAE3

# Text
C_TEXT_DARK   = {"red": 0.102, "green": 0.184, "blue": 0.294}   # #1A2F4B
C_TEXT_MID    = {"red": 0.408, "green": 0.486, "blue": 0.561}   # #687988
C_TEXT_LIGHT  = {"red": 0.616, "green": 0.682, "blue": 0.741}   # #9DAEBE

# Status colors
C_RED         = {"red": 0.906, "green": 0.298, "blue": 0.235}   # #E74C3C
C_ORANGE      = {"red": 0.953, "green": 0.580, "blue": 0.153}   # #F39327

# Aliases used in old code — map to new palette
C_DARK   = C_NAVY
C_MID    = C_NAVY_MED
C_LIGHT  = C_TEXT_LIGHT
C_HEADER = C_NAVY
C_MARTIN = C_BLUE
C_PERSON = C_GREEN


def _get_services():
    """Return (sheets, drive) using Jacques' OAuth credentials."""
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
    sheets = build("sheets", "v4", credentials=creds)
    drive  = build("drive",  "v3", credentials=creds)
    return sheets, drive


def _get_creds():
    """Return bare credentials (for Gmail reuse)."""
    _get_services()   # ensures token is refreshed/saved
    return Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)


def _find_shared_drive(drive) -> tuple[str | None, str | None]:
    """Return (id, name) for SHARED_DRIVE_NAME, or (None, None) if blank/not found."""
    if not SHARED_DRIVE_NAME:
        return None, None
    try:
        resp = drive.drives().list(pageSize=20, fields="drives(id,name)").execute()
        for d in resp.get("drives", []):
            if SHARED_DRIVE_NAME.lower() in d["name"].lower():
                return d["id"], d["name"]
    except Exception:
        pass
    return None, None


def _get_or_create_personal_folder(drive, name: str, parent_id: str = None) -> str:
    """Find or create a folder by name in My Drive (optionally inside parent_id)."""
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
         f"and trashed=false")
    if parent_id:
        q += f" and '{parent_id}' in parents"
    results = drive.files().list(q=q, fields="files(id,name)",
                                 supportsAllDrives=True,
                                 includeItemsFromAllDrives=True).execute()
    files   = results.get("files", [])
    if files:
        return files[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    folder = drive.files().create(body=body, fields="id", supportsAllDrives=True).execute()
    return folder["id"]


def _get_or_create_folder(drive) -> tuple[str, str | None]:
    """Return (coaching_folder_id, shared_drive_id or None)."""
    shared_drive_id, shared_drive_name = _find_shared_drive(drive)

    parent_id = None
    if shared_drive_id:
        parent_id = shared_drive_id
        print(f"  Using shared drive: '{shared_drive_name}'")
    else:
        # Find or create the "MJ Realty" parent folder in My Drive first
        if PERSONAL_FOLDER:
            parent_id = _get_or_create_personal_folder(drive, PERSONAL_FOLDER)
            print(f"  Saving inside '{PERSONAL_FOLDER}' folder in personal Google Drive")
        else:
            print(f"  Saving to personal Google Drive (root)")

    # Search for existing coaching subfolder (inside parent_id if set)
    q = (f"name='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' "
         f"and trashed=false"
         + (f" and '{parent_id}' in parents" if parent_id else ""))

    list_kwargs = {"q": q, "fields": "files(id,name)", "supportsAllDrives": True,
                   "includeItemsFromAllDrives": True}
    if shared_drive_id:
        list_kwargs.update({"corpora": "drive", "driveId": shared_drive_id})

    results = drive.files().list(**list_kwargs).execute()
    files   = results.get("files", [])
    if files:
        return files[0]["id"], shared_drive_id

    # Create the coaching subfolder inside parent
    body = {"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    folder = drive.files().create(body=body, fields="id", supportsAllDrives=True).execute()
    return folder["id"], shared_drive_id


def _week_label() -> str:
    """Return 'Week of Mon Apr 7, 2025' string."""
    today  = datetime.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return f"Week of {monday.strftime('%b %-d')} – {sunday.strftime('%b %-d, %Y')}"


def _find_existing_sheet(drive, folder_id: str, week_label: str,
                          shared_drive_id: str | None = None):
    q = (f"'{folder_id}' in parents "
         f"and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false")
    list_kwargs = {"q": q, "fields": "files(id,name,webViewLink)",
                   "supportsAllDrives": True, "includeItemsFromAllDrives": True}
    if shared_drive_id:
        list_kwargs.update({"corpora": "drive", "driveId": shared_drive_id})
    r = drive.files().list(**list_kwargs).execute()
    for f in r.get("files", []):
        if week_label in f["name"]:
            return f
    return None


def create_realtor_folder(realtor: dict) -> dict:
    """
    Find or create a personal Drive folder for a realtor and share it.
    Call this once when the realtor is first added to the system.
    Returns {"folder_id": ..., "folder_url": ...}
    """
    _, drive = _get_services()
    coaching_folder_id, shared_drive_id = _get_or_create_folder(drive)

    folder_id = _get_or_create_personal_folder(
        drive, realtor["name"], parent_id=coaching_folder_id
    )

    # Get the shareable link
    meta = drive.files().get(
        fileId=folder_id, fields="webViewLink", supportsAllDrives=True
    ).execute()
    folder_url = meta.get(
        "webViewLink",
        f"https://drive.google.com/drive/folders/{folder_id}"
    )

    # Share with anyone who has the link (writer = they can open & edit sheets inside)
    if not shared_drive_id:
        try:
            drive.permissions().create(
                fileId=folder_id,
                body={"role": "writer", "type": "anyone"},
                supportsAllDrives=True,
            ).execute()
        except Exception:
            pass  # Already shared or permission denied

    print(f"  Folder for '{realtor['name']}': {folder_url}")
    return {"folder_id": folder_id, "folder_url": folder_url}


def create_weekly_sheet(realtor: dict) -> dict:
    """
    Create (or reuse) a Google Sheet for `realtor` for the current week.
    Saves inside the realtor's personal subfolder (stored as realtor['folder_id']).
    Returns {"spreadsheet_id": ..., "url": ..., "week_label": ...}
    """
    sheets_svc, drive = _get_services()
    folder_id, shared_drive_id = _get_or_create_folder(drive)
    week_label = _week_label()

    # Use pre-provisioned folder_id if available, otherwise find/create on the fly
    if realtor.get("folder_id"):
        realtor_folder_id = realtor["folder_id"]
    else:
        realtor_folder_id = _get_or_create_personal_folder(
            drive, realtor["name"], parent_id=folder_id
        )

    # Reuse if already created this week
    existing = _find_existing_sheet(drive, realtor_folder_id, week_label,
                                    shared_drive_id=shared_drive_id)
    if existing:
        return {
            "spreadsheet_id": existing["id"],
            "url":            existing["webViewLink"],
            "week_label":     week_label,
            "reused":         True,
        }

    sheet_title = f"[{week_label}] {realtor['name']} — Coaching / Accountability"
    spreadsheet = sheets_svc.spreadsheets().create(body={
        "properties": {"title": sheet_title},
        "sheets": [
            {"properties": {"title": "🏠 Overview",       "index": 0}},
            {"properties": {"title": "📋 Weekly Strategy", "index": 1}},
            {"properties": {"title": "📊 Activity Log",   "index": 2}},
            {"properties": {"title": "📈 My History",     "index": 3}},
        ],
    }, fields="spreadsheetId,spreadsheetUrl").execute()

    sid = spreadsheet["spreadsheetId"]
    url = spreadsheet["spreadsheetUrl"]

    # Move into the realtor's personal subfolder
    file_meta = drive.files().get(
        fileId=sid, fields="parents", supportsAllDrives=True
    ).execute()
    prev_parents = ",".join(file_meta.get("parents", []))

    drive.files().update(
        fileId=sid,
        addParents=realtor_folder_id,
        removeParents=prev_parents,
        fields="id,parents",
        supportsAllDrives=True,
    ).execute()

    # If NOT in a shared drive, share with anyone who has the link as editor
    if not shared_drive_id:
        drive.permissions().create(
            fileId=sid,
            body={"role": "writer", "type": "anyone"},
            supportsAllDrives=True,
        ).execute()

    # Use per-realtor task list (enabled tasks only); fall back to COACHING_CHECKLIST
    if realtor.get("tasks"):
        all_tasks = [t for t in realtor["tasks"] if t.get("enabled", True)]
    else:
        all_tasks = list(COACHING_CHECKLIST)
    total_pts    = sum(t["points"] for t in all_tasks)
    martin_goals = realtor.get("martin_goals", "")

    _populate_overview(sheets_svc, sid, realtor, week_label, martin_goals, all_tasks, total_pts)
    _populate_checklist(sheets_svc, sid, realtor, week_label, all_tasks, total_pts)
    _populate_activity(sheets_svc, sid)
    _populate_history(sheets_svc, sid, realtor, all_tasks)

    return {
        "spreadsheet_id": sid,
        "url":            url,
        "week_label":     week_label,
        "reused":         False,
    }


# ── Helper: get sheet id by name ──────────────────────────────────────────────

def _sheet_id(ss, sid: str, name: str) -> int:
    meta = ss.get(spreadsheetId=sid, fields="sheets.properties").execute()
    return next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == name
    )


# ── Helper: cell range dict ───────────────────────────────────────────────────

def _rng(sh_id, r1, r2, c1, c2):
    return {"sheetId": sh_id, "startRowIndex": r1, "endRowIndex": r2,
            "startColumnIndex": c1, "endColumnIndex": c2}


# ── Helper: repeatCell request ────────────────────────────────────────────────

def _fmt(sh_id, r1, r2, c1, c2, *, bg=None, fg=None, bold=False, italic=False,
         font_size=None, h_align=None, wrap=False):
    fmt = {}
    if bg:
        fmt["backgroundColor"] = bg
    tf = {}
    if fg:
        tf["foregroundColor"] = fg
    if bold:
        tf["bold"] = True
    if italic:
        tf["italic"] = True
    if font_size:
        tf["fontSize"] = font_size
    if tf:
        fmt["textFormat"] = tf
    if h_align:
        fmt["horizontalAlignment"] = h_align
    if wrap:
        fmt["wrapStrategy"] = "WRAP"
    return {
        "repeatCell": {
            "range":  _rng(sh_id, r1, r2, c1, c2),
            "cell":   {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat",
        }
    }


# ── Helper: merge cells request ───────────────────────────────────────────────

def _merge(sh_id, r1, r2, c1, c2):
    return {"mergeCells": {"range": _rng(sh_id, r1, r2, c1, c2), "mergeType": "MERGE_ALL"}}


# ── Helper: set row height ────────────────────────────────────────────────────

def _row_height(sh_id, r1, r2, px):
    return {
        "updateDimensionProperties": {
            "range":      {"sheetId": sh_id, "dimension": "ROWS",
                           "startIndex": r1, "endIndex": r2},
            "properties": {"pixelSize": px},
            "fields":     "pixelSize",
        }
    }


# ── Helper: set column width ──────────────────────────────────────────────────

def _col_width(sh_id, c1, c2, px):
    return {
        "updateDimensionProperties": {
            "range":      {"sheetId": sh_id, "dimension": "COLUMNS",
                           "startIndex": c1, "endIndex": c2},
            "properties": {"pixelSize": px},
            "fields":     "pixelSize",
        }
    }


# ── Tab 1: Overview ───────────────────────────────────────────────────────────

def _populate_overview(sheets_svc, sid: str, realtor: dict, week_label: str,
                       martin_goals: str, all_tasks: list, total_pts: int):
    sheet_name = "🏠 Overview"
    ss         = sheets_svc.spreadsheets()
    sh_id      = _sheet_id(ss, sid, sheet_name)
    focus      = realtor.get("coaching_focus", "")

    score_formula  = "=SUM('📋 Weekly Strategy'!E5:E200)"
    pct_formula    = f"=IFERROR(ROUND(SUM('📋 Weekly Strategy'!E5:E200)/{total_pts}*100,0)&\"%\",\"0%\")"
    rating_formula = (
        f"=IF(IFERROR(SUM('📋 Weekly Strategy'!E5:E200)/{total_pts}*100,0)>=90,\"🏆 Excellent\","
        f"IF(IFERROR(SUM('📋 Weekly Strategy'!E5:E200)/{total_pts}*100,0)>=75,\"💪 Strong\","
        f"IF(IFERROR(SUM('📋 Weekly Strategy'!E5:E200)/{total_pts}*100,0)>=60,\"✅ On Track\","
        f"IF(IFERROR(SUM('📋 Weekly Strategy'!E5:E200)/{total_pts}*100,0)>=40,\"⚠️ Needs Work\","
        f"\"🚨 Off Track\"))))"
    )

    # Yearly goals
    goals        = realtor.get("yearly_goals", {})
    cons_gci     = goals.get("conservative_gci", 0)
    str_gci      = goals.get("stretch_gci", 0)
    total_deals  = goals.get("total_deals", 0)
    buyer_deals  = goals.get("buyer_deals", 0)
    seller_deals = goals.get("seller_deals", 0)
    cons_str     = f"${cons_gci:,.0f}" if cons_gci else "—"
    str_str      = f"${str_gci:,.0f}"  if str_gci  else "—"
    deals_str    = f"{total_deals} total  ({buyer_deals} buyers / {seller_deals} sellers)" if total_deals else "—"

    # Priorities (up to 5 lines)
    priorities_raw = realtor.get("priorities", "").strip()
    priority_lines = [l.strip() for l in priorities_raw.splitlines() if l.strip()][:5]
    while len(priority_lines) < 5:
        priority_lines.append("")

    #  Row layout (0-based index):
    #   0  – main title
    #   1  – realtor name
    #   2  – week + company
    #   3  – focus bar
    #   4  – spacer
    #   5  – 🎯 YEARLY TARGETS header
    #   6  – Conservative GCI / Stretch GCI values
    #   7  – Total Deals breakdown
    #   8  – spacer
    #   9  – MARTIN'S GOALS header
    #  10  – martin goals text
    #  11  – edit hint
    #  12  – spacer
    #  13  – PRIORITIES header
    #  14-18 – priority lines (5 rows)
    #  19  – spacer
    #  20  – SCORE header
    #  21  – score line
    #  22  – navigation hint

    rows = [
        ["COACHING / ACCOUNTABILITY", "", "", "", "", "", "", ""],          # 0
        [realtor["name"], "", "", "", "", "", "", ""],                       # 1
        [f"🗓  {week_label}", "", "", "", "MJ Realty Coaching", "", "", ""],# 2
        [f"📍  Coaching Focus:  {focus}", "", "", "", "", "", "", ""],       # 3
        [""] * 8,                                                            # 4 spacer
        ["🎯  2026 YEARLY TARGETS", "", "", "", "", "", "", ""],             # 5
        ["Conservative GCI", cons_str, "", "Stretch GCI", str_str, "", "", ""],  # 6
        ["Total Deals", deals_str, "", "", "", "", "", ""],                  # 7
        [""] * 8,                                                            # 8 spacer
        ["📌  MARTIN'S GOALS FOR YOU THIS WEEK", "", "", "", "", "", "", ""],# 9
        ["", martin_goals or "Martin will add your goals here before Sunday.", "", "", "", "", "", ""],  # 10
        ["", "✏️  Martin or you can edit this directly in the sheet", "", "", "", "", "", ""],           # 11
        [""] * 8,                                                            # 12 spacer
        ["📝  THIS WEEK'S PRIORITIES", "", "", "", "", "", "", ""],          # 13
        ["•", priority_lines[0], "", "", "", "", "", ""],                    # 14
        ["•", priority_lines[1], "", "", "", "", "", ""],                    # 15
        ["•", priority_lines[2], "", "", "", "", "", ""],                    # 16
        ["•", priority_lines[3], "", "", "", "", "", ""],                    # 17
        ["•", priority_lines[4], "", "", "", "", "", ""],                    # 18
        [""] * 8,                                                            # 19 spacer
        ["📊  THIS WEEK'S SCORE", "", "", "", "", "", "", ""],               # 20
        ["Score:", "", score_formula, f"/ {total_pts} pts  ·", pct_formula, "·", rating_formula, ""],  # 21
        ["→ Open the Weekly Strategy tab to complete your tasks. Score updates automatically.", "", "", "", "", "", "", ""],  # 22
    ]

    ss.values().update(
        spreadsheetId=sid,
        range=f"'{sheet_name}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    reqs = [
        # ── Dimensions ────────────────────────────────────────────────────
        _row_height(sh_id, 0, 1, 52),
        _row_height(sh_id, 1, 2, 32),
        _row_height(sh_id, 2, 3, 24),
        _row_height(sh_id, 3, 4, 24),
        _row_height(sh_id, 4, 5, 10),   # spacer
        _row_height(sh_id, 5, 6, 28),   # yearly targets header
        _row_height(sh_id, 6, 7, 28),   # GCI row
        _row_height(sh_id, 7, 8, 28),   # deals row
        _row_height(sh_id, 8, 9, 10),   # spacer
        _row_height(sh_id, 9, 10, 28),  # martin header
        _row_height(sh_id, 10, 11, 80), # martin text
        _row_height(sh_id, 11, 12, 20), # edit hint
        _row_height(sh_id, 12, 13, 10), # spacer
        _row_height(sh_id, 13, 14, 28), # priorities header
        _row_height(sh_id, 14, 19, 24), # priority rows
        _row_height(sh_id, 19, 20, 10), # spacer
        _row_height(sh_id, 20, 21, 28), # score header
        _row_height(sh_id, 21, 22, 40), # score line
        _row_height(sh_id, 22, 23, 22), # nav hint
        _col_width(sh_id, 0, 1, 170),
        _col_width(sh_id, 1, 5, 120),
        _col_width(sh_id, 5, 8, 100),

        # ── Merges ────────────────────────────────────────────────────────
        _merge(sh_id, 0, 1, 0, 8),
        _merge(sh_id, 1, 2, 0, 8),
        _merge(sh_id, 2, 3, 0, 4),
        _merge(sh_id, 2, 3, 4, 8),
        _merge(sh_id, 3, 4, 0, 8),
        _merge(sh_id, 4, 5, 0, 8),
        # yearly targets
        _merge(sh_id, 5, 6, 0, 8),
        _merge(sh_id, 6, 7, 3, 5),     # "Stretch GCI" label spans cols D-E
        _merge(sh_id, 6, 7, 5, 8),     # stretch value spans F-H
        _merge(sh_id, 7, 8, 1, 8),     # deals text spans B-H
        _merge(sh_id, 8, 9, 0, 8),
        # martin goals
        _merge(sh_id, 9, 10, 0, 8),
        _merge(sh_id, 10, 11, 1, 8),
        _merge(sh_id, 11, 12, 1, 8),
        _merge(sh_id, 12, 13, 0, 8),
        # priorities
        _merge(sh_id, 13, 14, 0, 8),
        _merge(sh_id, 14, 15, 1, 8),
        _merge(sh_id, 15, 16, 1, 8),
        _merge(sh_id, 16, 17, 1, 8),
        _merge(sh_id, 17, 18, 1, 8),
        _merge(sh_id, 18, 19, 1, 8),
        _merge(sh_id, 19, 20, 0, 8),
        # score
        _merge(sh_id, 20, 21, 0, 8),
        _merge(sh_id, 21, 22, 0, 1),
        _merge(sh_id, 21, 22, 1, 2),
        _merge(sh_id, 21, 22, 2, 3),
        _merge(sh_id, 21, 22, 3, 4),
        _merge(sh_id, 21, 22, 4, 5),
        _merge(sh_id, 21, 22, 5, 8),
        _merge(sh_id, 22, 23, 0, 8),

        # ── Row 0: main title ─────────────────────────────────────────────
        _fmt(sh_id, 0, 1, 0, 8, bg=C_NAVY, fg=C_WHITE, bold=True, font_size=20, h_align="CENTER"),

        # ── Row 1: realtor name ───────────────────────────────────────────
        _fmt(sh_id, 1, 2, 0, 8, bg=C_NAVY, fg=C_GOLD, bold=True, font_size=15, h_align="CENTER"),

        # ── Row 2: week + company ─────────────────────────────────────────
        _fmt(sh_id, 2, 3, 0, 4, bg=C_NAVY_MED, fg=C_TEXT_LIGHT, font_size=10),
        _fmt(sh_id, 2, 3, 4, 8, bg=C_NAVY_MED, fg=C_TEXT_LIGHT, font_size=10, h_align="RIGHT"),

        # ── Row 3: focus bar ──────────────────────────────────────────────
        _fmt(sh_id, 3, 4, 0, 8, bg=C_NAVY_LIGHT, fg=C_TEXT_DARK, italic=True, font_size=10, h_align="CENTER"),

        # ── Row 4: spacer ─────────────────────────────────────────────────
        _fmt(sh_id, 4, 5, 0, 8, bg=C_GRAY_LIGHT),

        # ── Rows 5–7: yearly targets ──────────────────────────────────────
        _fmt(sh_id, 5, 6, 0, 8, bg=C_GOLD, fg=C_NAVY, bold=True, font_size=11),
        _fmt(sh_id, 6, 7, 0, 1, bg=C_GOLD_LIGHT, fg=C_TEXT_MID, bold=True, font_size=10),
        _fmt(sh_id, 6, 7, 1, 3, bg=C_GOLD_LIGHT, fg=C_NAVY, bold=True, font_size=13, h_align="CENTER"),
        _fmt(sh_id, 6, 7, 3, 5, bg=C_GOLD_LIGHT, fg=C_TEXT_MID, bold=True, font_size=10),
        _fmt(sh_id, 6, 7, 5, 8, bg=C_GOLD_LIGHT, fg=C_NAVY, bold=True, font_size=13, h_align="CENTER"),
        _fmt(sh_id, 7, 8, 0, 1, bg=C_GOLD_LIGHT, fg=C_TEXT_MID, bold=True, font_size=10),
        _fmt(sh_id, 7, 8, 1, 8, bg=C_GOLD_LIGHT, fg=C_NAVY, font_size=11),

        # ── Row 8: spacer ─────────────────────────────────────────────────
        _fmt(sh_id, 8, 9, 0, 8, bg=C_GRAY_LIGHT),

        # ── Rows 9–11: Martin's goals ─────────────────────────────────────
        _fmt(sh_id, 9, 10, 0, 8, bg=C_BLUE, fg=C_WHITE, bold=True, font_size=11),
        _fmt(sh_id, 10, 11, 0, 1, bg=C_BLUE_LIGHT, fg=C_BLUE, bold=True, font_size=10),
        _fmt(sh_id, 10, 11, 1, 8, bg=C_BLUE_LIGHT, fg=C_TEXT_DARK, font_size=11, wrap=True),
        _fmt(sh_id, 11, 12, 0, 8, bg=C_BLUE_LIGHT, fg=C_TEXT_MID, italic=True, font_size=9),

        # ── Row 12: spacer ────────────────────────────────────────────────
        _fmt(sh_id, 12, 13, 0, 8, bg=C_GRAY_LIGHT),

        # ── Rows 13–18: priorities ────────────────────────────────────────
        _fmt(sh_id, 13, 14, 0, 8, bg=C_GREEN, fg=C_WHITE, bold=True, font_size=11),
        _fmt(sh_id, 14, 19, 0, 1, bg=C_GREEN_LIGHT, fg=C_GREEN, bold=True, font_size=12, h_align="CENTER"),
        _fmt(sh_id, 14, 19, 1, 8, bg=C_GREEN_LIGHT, fg=C_TEXT_DARK, font_size=11),

        # ── Row 19: spacer ────────────────────────────────────────────────
        _fmt(sh_id, 19, 20, 0, 8, bg=C_GRAY_LIGHT),

        # ── Row 20: score header ──────────────────────────────────────────
        _fmt(sh_id, 20, 21, 0, 8, bg=C_NAVY, fg=C_WHITE, bold=True, font_size=11),

        # ── Row 21: score line ────────────────────────────────────────────
        _fmt(sh_id, 21, 22, 0, 1, bg=C_OFF_WHITE, fg=C_TEXT_MID, bold=True, font_size=10, h_align="RIGHT"),
        _fmt(sh_id, 21, 22, 1, 2, bg=C_OFF_WHITE, fg=C_NAVY, bold=True, font_size=20, h_align="CENTER"),
        _fmt(sh_id, 21, 22, 2, 3, bg=C_OFF_WHITE, fg=C_TEXT_MID, font_size=10, h_align="LEFT"),
        _fmt(sh_id, 21, 22, 3, 4, bg=C_OFF_WHITE, fg=C_GREEN, bold=True, font_size=16, h_align="CENTER"),
        _fmt(sh_id, 21, 22, 4, 5, bg=C_OFF_WHITE, fg=C_TEXT_LIGHT, font_size=12, h_align="CENTER"),
        _fmt(sh_id, 21, 22, 5, 8, bg=C_OFF_WHITE, fg=C_NAVY_MED, bold=True, font_size=13, h_align="CENTER"),

        # ── Row 22: nav hint ──────────────────────────────────────────────
        _fmt(sh_id, 22, 23, 0, 8, bg=C_GRAY_LIGHT, fg=C_TEXT_MID, italic=True, font_size=9, h_align="CENTER"),
    ]

    ss.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()


# ── Tab 2: Weekly Strategy ────────────────────────────────────────────────────

def _populate_checklist(sheets_svc, sid: str, realtor: dict, week_label: str,
                        all_tasks: list, total_pts: int):
    sheet_name = "📋 Weekly Strategy"
    ss         = sheets_svc.spreadsheets()
    sh_id      = _sheet_id(ss, sid, sheet_name)

    # Group tasks by category (custom tasks merge into their named category)
    from collections import defaultdict
    seen_cats    = []
    tasks_by_cat = defaultdict(list)
    for t in all_tasks:
        if t["category"] not in seen_cats:
            seen_cats.append(t["category"])
        tasks_by_cat[t["category"]].append(t)
    sorted_tasks = []
    for cat in seen_cats:
        sorted_tasks.extend(tasks_by_cat[cat])

    rows = [
        ["📋  WEEKLY STRATEGY", "", "", "", ""],
        ["SCORE:", "", f"/ {total_pts} pts", "", ""],
        ["", "", "", "", ""],
        ["CATEGORY", "TASK", "DONE?", "PTS", "EARNED"],
    ]

    # Always write category on every task row so SUMIF in History tab works
    for item in sorted_tasks:
        rows.append([item["category"], item["task"], "☐  No", item["points"], ""])

    rows.append(["", "", "", "", ""])  # spacer before totals

    first_data_1idx = 5
    last_data_1idx  = first_data_1idx + len(sorted_tasks) - 1
    total_row_idx   = len(rows)
    total_row_1idx  = total_row_idx + 1

    rows.append(["", "TOTAL SCORE", "", total_pts,
                 f"=SUM(E{first_data_1idx}:E{last_data_1idx})"])
    rows.append(["", "COMPLETION", "", "",
                 f"=IFERROR(ROUND(E{total_row_1idx}/D{total_row_1idx}*100,0)&\"%\",\"0%\")"])

    ss.values().update(
        spreadsheetId=sid,
        range=f"'{sheet_name}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    # Score summary bar formulas
    ss.values().batchUpdate(spreadsheetId=sid, body={
        "valueInputOption": "USER_ENTERED",
        "data": [
            {"range": f"'{sheet_name}'!B2",
             "values": [[f"=SUM(E{first_data_1idx}:E{last_data_1idx})"]]},
            {"range": f"'{sheet_name}'!D2",
             "values": [[f"=IFERROR(ROUND(SUM(E{first_data_1idx}:E{last_data_1idx})/{total_pts}*100,0)&\"%\",\"0%\")"]]},
            {"range": f"'{sheet_name}'!E2",
             "values": [[
                 f"=IF(IFERROR(SUM(E{first_data_1idx}:E{last_data_1idx})/{total_pts}*100,0)>=90,\"🏆 Excellent\","
                 f"IF(IFERROR(SUM(E{first_data_1idx}:E{last_data_1idx})/{total_pts}*100,0)>=75,\"💪 Strong\","
                 f"IF(IFERROR(SUM(E{first_data_1idx}:E{last_data_1idx})/{total_pts}*100,0)>=60,\"✅ On Track\","
                 f"IF(IFERROR(SUM(E{first_data_1idx}:E{last_data_1idx})/{total_pts}*100,0)>=40,\"⚠️ Needs Work\","
                 f"\"🚨 Off Track\"))))"
             ]]},
        ],
    }).execute()

    # Earned formulas per task row
    data_start_0   = 4
    earned_updates = []
    for i in range(len(sorted_tasks)):
        abs_1 = data_start_0 + i + 1  # 1-indexed
        earned_updates.append({
            "range":  f"'{sheet_name}'!E{abs_1}",
            "values": [[f'=IF(C{abs_1}="✅  Yes",D{abs_1},0)']],
        })
    if earned_updates:
        ss.values().batchUpdate(spreadsheetId=sid, body={
            "valueInputOption": "USER_ENTERED",
            "data": earned_updates,
        }).execute()

    first_task_0 = data_start_0
    last_task_0  = first_task_0 + len(sorted_tasks)

    reqs = [
        _col_width(sh_id, 0, 1, 140),
        _col_width(sh_id, 1, 2, 400),
        _col_width(sh_id, 2, 3, 130),
        _col_width(sh_id, 3, 4, 60),
        _col_width(sh_id, 4, 5, 90),

        # Row 0: title — navy bg, white
        _row_height(sh_id, 0, 1, 44),
        _merge(sh_id, 0, 1, 0, 5),
        _fmt(sh_id, 0, 1, 0, 5, bg=C_NAVY, fg=C_WHITE, bold=True, font_size=16, h_align="CENTER"),

        # Row 1: score bar
        _row_height(sh_id, 1, 2, 32),
        _fmt(sh_id, 1, 2, 0, 1, bg=C_NAVY_MED, fg=C_TEXT_LIGHT, bold=True, font_size=9, h_align="RIGHT"),
        _fmt(sh_id, 1, 2, 1, 2, bg=C_NAVY_MED, fg=C_GOLD, bold=True, font_size=18),
        _fmt(sh_id, 1, 2, 2, 3, bg=C_NAVY_MED, fg=C_TEXT_LIGHT, font_size=10),
        _fmt(sh_id, 1, 2, 3, 4, bg=C_NAVY_MED, fg=C_GREEN, bold=True, font_size=14),
        _fmt(sh_id, 1, 2, 4, 5, bg=C_NAVY_MED, fg=C_WHITE, font_size=11),

        # Row 2: spacer
        _row_height(sh_id, 2, 3, 8),
        _fmt(sh_id, 2, 3, 0, 5, bg=C_GRAY_LIGHT),

        # Row 3: column headers
        _fmt(sh_id, 3, 4, 0, 5, bg=C_NAVY_LIGHT, fg=C_TEXT_DARK, bold=True, font_size=10),

        # Freeze top 4 rows
        {"updateSheetProperties": {
            "properties": {"sheetId": sh_id, "gridProperties": {"frozenRowCount": 4}},
            "fields":     "gridProperties.frozenRowCount",
        }},
    ]

    # Task rows: alternating colors, category label italic/muted
    for i, task in enumerate(sorted_tasks):
        abs_0  = data_start_0 + i
        row_bg = C_WHITE if i % 2 == 0 else C_OFF_WHITE
        reqs.append(_fmt(sh_id, abs_0, abs_0 + 1, 0, 5, bg=row_bg, fg=C_TEXT_DARK, font_size=10))
        reqs.append(_fmt(sh_id, abs_0, abs_0 + 1, 0, 1, bg=row_bg, fg=C_TEXT_MID, font_size=9, italic=True))
        reqs.append(_fmt(sh_id, abs_0, abs_0 + 1, 1, 2, bg=row_bg, fg=C_TEXT_DARK, font_size=10, wrap=True))
        reqs.append(_row_height(sh_id, abs_0, abs_0 + 1, 26))

    # Totals rows
    reqs.append(_fmt(sh_id, total_row_idx, total_row_idx + 1, 0, 5,
                     bg=C_NAVY, fg=C_WHITE, bold=True))
    reqs.append(_fmt(sh_id, total_row_idx + 1, total_row_idx + 2, 0, 5,
                     bg=C_NAVY, fg=C_GOLD, bold=True))

    # Data validation dropdown
    reqs.append({"setDataValidation": {
        "range": {"sheetId": sh_id, "startRowIndex": first_task_0,
                  "endRowIndex": last_task_0, "startColumnIndex": 2, "endColumnIndex": 3},
        "rule": {
            "condition": {"type": "ONE_OF_LIST", "values": [
                {"userEnteredValue": "✅  Yes"},
                {"userEnteredValue": "☐  No"},
            ]},
            "showCustomUi": True, "strict": True,
        },
    }})

    # Conditional formatting: light green tint on completed rows
    reqs.append({"addConditionalFormatRule": {
        "rule": {
            "ranges": [{"sheetId": sh_id, "startRowIndex": first_task_0,
                        "endRowIndex": last_task_0, "startColumnIndex": 0, "endColumnIndex": 5}],
            "booleanRule": {
                "condition": {"type": "CUSTOM_FORMULA",
                              "values": [{"userEnteredValue": f"=$C{first_task_0+1}=\"✅  Yes\""}]},
                "format": {"backgroundColor": C_GREEN_LIGHT},
            },
        },
        "index": 0,
    }})

    ss.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()


# ── Tab 3: Activity Log ───────────────────────────────────────────────────────

def _populate_activity(sheets_svc, sid: str):
    sheet_name = "📊 Activity Log"
    ss         = sheets_svc.spreadsheets()
    sh_id      = _sheet_id(ss, sid, sheet_name)

    num_cols = len(ACTIVITY_LOG_COLUMNS)

    rows = [
        ["📊 Daily Activity Log — Fill in each day"] + [""] * (num_cols - 1),
        ACTIVITY_LOG_COLUMNS,
    ]
    for day in DAYS_OF_WEEK:
        rows.append([day] + [""] * (num_cols - 1))

    rows.append([""] * num_cols)

    # Totals row (day rows start at index 2, end at 2+len(DAYS_OF_WEEK)-1)
    day_start_1 = 3   # 1-based row of first day
    day_end_1   = 2 + len(DAYS_OF_WEEK)
    totals = ["WEEKLY TOTALS"]
    for col_idx in range(1, num_cols - 1):
        col_letter = chr(ord("A") + col_idx)
        totals.append(f"=SUM({col_letter}{day_start_1}:{col_letter}{day_end_1})")
    totals.append("")  # Notes column — no sum
    rows.append(totals)

    ss.values().update(
        spreadsheetId=sid,
        range=f"'{sheet_name}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    totals_row_0 = 2 + len(DAYS_OF_WEEK) + 1  # 0-based index of totals row

    reqs = [
        # Column widths
        _col_width(sh_id, 0, 1, 130),
        _col_width(sh_id, 1, num_cols - 1, 120),
        _col_width(sh_id, num_cols - 1, num_cols, 280),

        # Row 0: title
        _merge(sh_id, 0, 1, 0, num_cols),
        _row_height(sh_id, 0, 1, 40),
        _fmt(sh_id, 0, 1, 0, num_cols, bg=C_NAVY, fg=C_WHITE, bold=True, font_size=14),

        # Row 1: column headers
        _fmt(sh_id, 1, 2, 0, num_cols, bg=C_NAVY_LIGHT, fg=C_TEXT_DARK, bold=True, font_size=10),

        # Day rows
        _row_height(sh_id, 2, 2 + len(DAYS_OF_WEEK), 28),
        _fmt(sh_id, 2, 2 + len(DAYS_OF_WEEK), 0, num_cols, fg=C_TEXT_DARK, font_size=10),

        # Totals row
        _fmt(sh_id, totals_row_0, totals_row_0 + 1, 0, num_cols,
             bg=C_NAVY, fg=C_GOLD, bold=True),

        # Freeze header rows
        {"updateSheetProperties": {
            "properties": {"sheetId": sh_id, "gridProperties": {"frozenRowCount": 2}},
            "fields":     "gridProperties.frozenRowCount",
        }},
    ]

    for d_i in range(len(DAYS_OF_WEEK)):
        d_bg = C_WHITE if d_i % 2 == 0 else C_OFF_WHITE
        reqs.append(_fmt(sh_id, 2+d_i, 3+d_i, 0, num_cols, bg=d_bg, fg=C_TEXT_DARK, font_size=10))

    ss.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()


# ── Tab 4: My History ─────────────────────────────────────────────────────────

def _populate_history(sheets_svc, sid: str, realtor: dict, all_tasks: list):
    sheet_name    = "📈 My History"
    ss            = sheets_svc.spreadsheets()
    sh_id         = _sheet_id(ss, sid, sheet_name)
    score_history = realtor.get("score_history", [])

    # Unique categories in original order
    from collections import defaultdict
    seen_cats    = []
    tasks_by_cat = defaultdict(list)
    for t in all_tasks:
        if t["category"] not in seen_cats:
            seen_cats.append(t["category"])
        tasks_by_cat[t["category"]].append(t)

    # ── Build rows ────────────────────────────────────────────────────────────
    rows = [
        # row 0: title
        ["📈  MY SCORE HISTORY", "", "", "", ""],
        # row 1: subtitle
        ["Category breakdown (live) + weekly score history", "", "", "", ""],
        # row 2: spacer
        ["", "", "", "", ""],
        # row 3: category section header
        ["📊  THIS WEEK — CATEGORY BREAKDOWN", "", "", "", ""],
        # row 4: category column headers
        ["CATEGORY", "EARNED", "OUT OF", "% THIS WEEK", "RATING"],
    ]

    # Category rows (rows 5 .. 5+n, 1-indexed)
    cat_row_start_1idx = len(rows) + 1  # 1-indexed start of first category row
    for i, cat in enumerate(seen_cats):
        row_1idx = cat_row_start_1idx + i
        earned_f = f"=SUMIF('📋 Weekly Strategy'!$A:$A,\"{cat}\",'📋 Weekly Strategy'!$E:$E)"
        total_f  = f"=SUMIF('📋 Weekly Strategy'!$A:$A,\"{cat}\",'📋 Weekly Strategy'!$D:$D)"
        pct_f    = f"=IFERROR(ROUND(B{row_1idx}/C{row_1idx}*100,0)&\"%\",\"0%\")"
        rating_f = (
            f"=IF(IFERROR(B{row_1idx}/C{row_1idx}*100,0)>=90,\"🏆 Excellent\","
            f"IF(IFERROR(B{row_1idx}/C{row_1idx}*100,0)>=75,\"💪 Strong\","
            f"IF(IFERROR(B{row_1idx}/C{row_1idx}*100,0)>=60,\"✅ On Track\","
            f"IF(IFERROR(B{row_1idx}/C{row_1idx}*100,0)>=40,\"⚠️ Needs Work\","
            f"\"🚨 Off Track\"))))"
        )
        rows.append([cat, earned_f, total_f, pct_f, rating_f])

    cat_section_end_0 = len(rows)  # 0-indexed row after last category row

    # Spacer + weekly history section
    rows.append(["", "", "", "", ""])  # spacer
    rows.append(["📅  WEEKLY SCORE HISTORY", "", "", "", ""])
    rows.append(["WEEK", "SCORE", "OUT OF", "%", "RATING"])

    history_header_0 = len(rows) - 1  # 0-indexed row of history column headers
    history_data_0   = len(rows)      # 0-indexed row of first history data row

    if score_history:
        for h in score_history:
            rows.append([
                h.get("week_label", ""),
                h.get("score", ""),
                h.get("total_possible", ""),
                str(h.get("percentage", "")) + "%",
                h.get("rating_label", ""),
            ])
    else:
        rows.append(["No history yet — scores will appear here after weekly reports",
                     "", "", "", ""])

    ss.values().update(
        spreadsheetId=sid,
        range=f"'{sheet_name}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    # ── Formatting ────────────────────────────────────────────────────────────
    cat_data_start_0 = 5   # 0-indexed first category data row
    num_cats         = len(seen_cats)

    reqs = [
        # Column widths
        _col_width(sh_id, 0, 1, 230),
        _col_width(sh_id, 1, 2, 80),
        _col_width(sh_id, 2, 3, 80),
        _col_width(sh_id, 3, 4, 100),
        _col_width(sh_id, 4, 5, 140),

        # Row 0: main title
        _row_height(sh_id, 0, 1, 44),
        _merge(sh_id, 0, 1, 0, 5),
        _fmt(sh_id, 0, 1, 0, 5, bg=C_NAVY, fg=C_WHITE, bold=True, font_size=16,
             h_align="CENTER"),

        # Row 1: subtitle
        _merge(sh_id, 1, 2, 0, 5),
        _fmt(sh_id, 1, 2, 0, 5, bg=C_NAVY_LIGHT, fg=C_TEXT_DARK, italic=True, font_size=9,
             h_align="CENTER"),

        # Row 2: spacer
        _row_height(sh_id, 2, 3, 10),
        _fmt(sh_id, 2, 3, 0, 5, bg=C_GRAY_LIGHT),

        # Row 3: category section header
        _row_height(sh_id, 3, 4, 28),
        _merge(sh_id, 3, 4, 0, 5),
        _fmt(sh_id, 3, 4, 0, 5, bg=C_BLUE, fg=C_WHITE, bold=True, font_size=11,
             h_align="LEFT"),

        # Row 4: category column headers
        _fmt(sh_id, 4, 5, 0, 5, bg=C_BLUE_LIGHT, fg=C_TEXT_DARK, bold=True, font_size=10),
    ]

    # Category data rows (alternating)
    for i in range(num_cats):
        r0     = cat_data_start_0 + i
        row_bg = C_WHITE if i % 2 == 0 else C_OFF_WHITE
        reqs.append(_fmt(sh_id, r0, r0 + 1, 0, 5, bg=row_bg, fg=C_TEXT_DARK, font_size=10))
        reqs.append(_fmt(sh_id, r0, r0 + 1, 0, 1, bg=row_bg, fg=C_NAVY_MED, bold=True, font_size=10))
        reqs.append(_row_height(sh_id, r0, r0 + 1, 26))
        # % column: green if formula resolves >=75, handled by color below
        reqs.append(_fmt(sh_id, r0, r0 + 1, 3, 4, bg=row_bg, fg=C_NAVY_MED, bold=True, font_size=11))
        reqs.append(_fmt(sh_id, r0, r0 + 1, 4, 5, bg=row_bg, fg=C_TEXT_MID, font_size=10))

    # Spacer row between sections
    spacer_0 = cat_section_end_0
    reqs.append(_row_height(sh_id, spacer_0, spacer_0 + 1, 10))
    reqs.append(_fmt(sh_id, spacer_0, spacer_0 + 1, 0, 5, bg=C_GRAY_LIGHT))

    # Weekly history section header
    hist_header_sec_0 = spacer_0 + 1
    reqs.append(_row_height(sh_id, hist_header_sec_0, hist_header_sec_0 + 1, 28))
    reqs.append(_merge(sh_id, hist_header_sec_0, hist_header_sec_0 + 1, 0, 5))
    reqs.append(_fmt(sh_id, hist_header_sec_0, hist_header_sec_0 + 1, 0, 5,
                     bg=C_NAVY, fg=C_WHITE, bold=True, font_size=11, h_align="LEFT"))

    # History column headers
    reqs.append(_fmt(sh_id, history_header_0, history_header_0 + 1, 0, 5,
                     bg=C_NAVY_LIGHT, fg=C_TEXT_DARK, bold=True, font_size=10))

    if not score_history:
        reqs.append(_merge(sh_id, history_data_0, history_data_0 + 1, 0, 5))
        reqs.append(_fmt(sh_id, history_data_0, history_data_0 + 1, 0, 5,
                         bg=C_OFF_WHITE, fg=C_TEXT_MID, italic=True, h_align="CENTER"))
    else:
        for i, h in enumerate(score_history):
            row_0 = history_data_0 + i
            bg    = C_WHITE if i % 2 == 0 else C_OFF_WHITE
            reqs.append(_fmt(sh_id, row_0, row_0 + 1, 0, 5, bg=bg, fg=C_TEXT_DARK,
                             font_size=10))
            pct = h.get("percentage", 0)
            pct_fg = C_GREEN if pct >= 75 else (C_GOLD if pct >= 60 else C_RED)
            reqs.append(_fmt(sh_id, row_0, row_0 + 1, 3, 4, bg=bg, fg=pct_fg, bold=True))

    ss.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()


# ── Read back sheet data for Monday report ────────────────────────────────────

def read_sheet_data(spreadsheet_id: str) -> dict:
    """
    Read the checklist score and activity log from a sheet.
    Returns a dict with score, completed tasks, activity totals, notes.
    """
    sheets_svc, _ = _get_services()
    ss             = sheets_svc.spreadsheets()

    checklist_range = "'📋 Weekly Strategy'!A1:E200"
    activity_range  = "'📊 Activity Log'!A1:H20"
    overview_range  = "'🏠 Overview'!A1:H20"

    try:
        checklist_vals = ss.values().get(
            spreadsheetId=spreadsheet_id, range=checklist_range
        ).execute().get("values", [])
    except Exception:
        checklist_vals = []

    try:
        activity_vals = ss.values().get(
            spreadsheetId=spreadsheet_id, range=activity_range
        ).execute().get("values", [])
    except Exception:
        activity_vals = []

    try:
        overview_vals = ss.values().get(
            spreadsheetId=spreadsheet_id, range=overview_range
        ).execute().get("values", [])
    except Exception:
        overview_vals = []

    # ── Parse checklist ───────────────────────────────────────────────────────
    # Header is 4 rows (0-3); data starts at index 4 (0-based).
    # Stop at the first blank row (the spacer before totals).
    score      = 0
    total_pts  = sum(i["points"] for i in COACHING_CHECKLIST)
    completed  = []
    incomplete = []

    for row in checklist_vals[4:]:
        if not any(row):
            break  # spacer row → end of tasks
        task      = row[1] if len(row) > 1 else ""
        done_flag = row[2] if len(row) > 2 else ""
        pts       = 0
        if len(row) > 3:
            try:
                pts = int(row[3])
            except (ValueError, TypeError):
                pts = 0
        if "Yes" in done_flag:
            score += pts
            if task:
                completed.append(task)
        else:
            if task:
                incomplete.append(task)

    # ── Parse activity totals ─────────────────────────────────────────────────
    activity_totals = {}
    if len(activity_vals) >= 2:
        headers = activity_vals[1] if len(activity_vals) > 1 else []
        for row in activity_vals[2:]:
            if row and row[0] == "WEEKLY TOTALS":
                for i, h in enumerate(headers[1:], 1):
                    try:
                        activity_totals[h] = int(row[i]) if i < len(row) else 0
                    except (ValueError, IndexError):
                        activity_totals[h] = 0
                break

    # ── Parse Martin's note from Overview tab row 7 (index 6), col B (index 1) ──
    note_to_martin = ""
    if len(overview_vals) > 6:
        row7 = overview_vals[6]
        if len(row7) > 1:
            note_to_martin = row7[1]

    pct = round(score / total_pts * 100) if total_pts else 0
    return {
        "score":           score,
        "total_possible":  total_pts,
        "percentage":      pct,
        "completed":       completed,
        "incomplete":      incomplete,
        "activity_totals": activity_totals,
        "note_to_martin":  note_to_martin,
    }
