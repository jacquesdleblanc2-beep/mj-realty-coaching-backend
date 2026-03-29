# dashboard.py — MJ Realty Coaching System — Streamlit Dashboard

import os
import json
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="MJ Realty — Coaching System",
    page_icon="🏠",
    layout="wide",
)

LOG_PATH = os.path.join(os.path.dirname(__file__), "send_log.json")


def _load_log():
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _week_label():
    today  = datetime.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return f"Week of {monday.strftime('%b %-d')} – {sunday.strftime('%b %-d, %Y')}"


# ── Session state ─────────────────────────────────────────────────────────────
DEFAULTS = {
    "sunday_result":  None,
    "monday_result":  None,
    "running":        False,
    "last_action":    None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#0f0f1a,#1a1a35);
            padding:22px 28px;border-radius:14px;margin-bottom:22px;
            border:1px solid #2a2a4a;">
  <h1 style="color:white;margin:0;font-size:1.9em;letter-spacing:0.5px;">
    🏠 MJ Realty — Coaching System
  </h1>
  <p style="color:#7a8aaa;margin:4px 0 0;font-size:0.95em;">
    Weekly accountability sheets · Automated Sunday emails · Monday reports to Martin
  </p>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    dry_run = st.toggle("🧪 Dry Run", value=True,
                        help="ON = no real emails sent. OFF = live Gmail sending.")

    st.markdown("---")
    st.markdown("### 🔑 Credentials")

    def _badge(label, ok):
        color = "#1a5c2a" if ok else "#7a1a1a"
        sym   = "✓" if ok else "✕"
        st.markdown(
            f'<div style="background:{color};color:white;padding:4px 10px;'
            f'border-radius:8px;font-size:0.82em;margin:3px 0;">{sym} {label}</div>',
            unsafe_allow_html=True,
        )

    _CREDS_DIR = os.path.join(os.path.dirname(__file__), "credentials")
    _badge("Gmail / Google Account",  bool(os.getenv("GMAIL_SENDER")))
    _badge("Martin Email",            bool(os.getenv("MARTIN_EMAIL")))
    _badge("OAuth credentials file",  os.path.exists(os.path.join(_CREDS_DIR, "oauth_credentials.json")))
    _badge("Google token (logged in)", os.path.exists(os.path.join(_CREDS_DIR, "google_token.json")))

    st.markdown("---")
    st.markdown("### 📅 Schedule")
    st.markdown("""
- **Sunday 8:00 AM** → Send reminder emails to all realtors
- **Monday 7:00 AM** → Collect scores + create new sheets + send report

Run `python scheduler.py` to start auto-schedule.
    """)

    st.markdown("---")
    st.markdown("### 👥 Realtors")
    from config import REALTORS
    for r in REALTORS:
        st.markdown(f"- **{r['name']}** — {r['coaching_focus']}")


# ── Controls ──────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 2, 1])

sunday_clicked = col1.button(
    "📨 Send Sunday Reminders",
    type="primary",
    use_container_width=True,
    help="Sends each realtor a reminder email with their sheet link. Runs automatically Sunday at 8 AM.",
)
monday_clicked = col2.button(
    "📤 Send New Sheets + Report (Monday)",
    use_container_width=True,
    help="Create next week's sheets, email realtors, and send Martin's report. Runs automatically Monday at 7 AM.",
)
if col3.button("↺ Reset", use_container_width=True):
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    st.rerun()

if st.session_state["last_action"]:
    st.caption(f"Last action: {st.session_state['last_action']}")

st.markdown("---")


# ── Sunday reminder pipeline ──────────────────────────────────────────────────
if sunday_clicked:
    from pipeline import run_sunday_reminder

    with st.status("📨 Sending Sunday reminder emails to realtors…",
                   expanded=True) as status:
        def _cb(msg):
            st.write(msg)

        try:
            result = run_sunday_reminder(dry_run=dry_run, progress_cb=_cb)
            st.session_state["sunday_result"] = result
            st.session_state["last_action"]   = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " — Sunday reminders sent"
            reminded = len(result.get("reminded", []))
            if result.get("errors"):
                status.update(label="⚠️ Sunday reminders completed with errors", state="error")
            else:
                status.update(label=f"✅ Done — {reminded} reminder{'s' if reminded != 1 else ''} sent", state="complete")
        except Exception as e:
            st.write(f"❌ Pipeline error: {e}")
            status.update(label="Pipeline failed", state="error")

    st.rerun()


# ── Monday pipeline ───────────────────────────────────────────────────────────
if monday_clicked:
    from pipeline import run_monday_pipeline

    with st.status("📤 Monday Pipeline — Creating new sheets & emailing realtors + Martin…",
                   expanded=True) as status:
        def _cb(msg):
            st.write(msg)

        try:
            result = run_monday_pipeline(dry_run=dry_run, progress_cb=_cb)
            st.session_state["monday_result"] = result
            st.session_state["last_action"]   = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " — Monday sheets + report"
            sheets_count = len(result.get("sheets", []))
            emails_count = len(result.get("emails", []))
            status.update(
                label=f"✅ Done — {sheets_count} sheets created, {emails_count} emails sent",
                state="complete",
            )
        except Exception as e:
            st.write(f"❌ Pipeline error: {e}")
            status.update(label="Pipeline failed", state="error")

    st.rerun()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_realtors, tab_sunday, tab_monday, tab_checklist = st.tabs([
    "📊 Overview & History", "👥 Realtors", "📥 Sunday Collection", "📤 Monday Report", "📝 Weekly Strategy"
])


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Overview & History
# ══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    from config import load_realtors, score_label, COACHING_CHECKLIST
    from collections import OrderedDict

    realtors = load_realtors()

    if not realtors:
        st.info("No realtors yet. Add one in the Realtors tab.")
    else:
        # Realtor selector if multiple
        if len(realtors) > 1:
            realtor_names = [r["name"] for r in realtors]
            selected_name = st.selectbox("Select realtor", realtor_names, key="overview_select")
            r = next(rt for rt in realtors if rt["name"] == selected_name)
        else:
            r = realtors[0]

        col_left, col_right = st.columns([3, 2], gap="large")

        # ── LEFT: This week ───────────────────────────────────────────────────
        with col_left:
            st.markdown(
                f"<h3 style='margin-bottom:2px;'>👤 {r['name']}</h3>"
                f"<p style='color:#7a8aaa;margin:0 0 16px;font-size:0.9em;'>{r.get('coaching_focus','')}</p>",
                unsafe_allow_html=True,
            )

            # ── Yearly Goals ─────────────────────────────────────────────────
            goals = r.get("yearly_goals", {})
            conservative = goals.get("conservative_gci", 0)
            stretch      = goals.get("stretch_gci", 0)
            total_deals  = goals.get("total_deals", 0)
            buyer_deals  = goals.get("buyer_deals", 0)
            seller_deals = goals.get("seller_deals", 0)

            st.markdown("""
<div style="background:linear-gradient(135deg,#0d1f35,#162a45);border:1px solid #2a3f5a;
            border-radius:12px;padding:18px 20px;margin-bottom:18px;">
  <p style="color:#4da6ff;font-weight:700;font-size:0.78em;text-transform:uppercase;
            letter-spacing:1px;margin:0 0 12px;">🎯 2026 Targets</p>
""", unsafe_allow_html=True)

            if conservative or stretch or total_deals:
                yg1, yg2, yg3 = st.columns(3)
                yg1.metric("Conservative GCI", f"${conservative:,.0f}" if conservative else "—")
                yg2.metric("Stretch GCI",      f"${stretch:,.0f}"      if stretch      else "—")
                yg3.metric(
                    "Total Deals",
                    f"{total_deals}" if total_deals else "—",
                    delta=f"{buyer_deals}B / {seller_deals}S" if total_deals else None,
                    delta_color="off",
                )
            else:
                st.caption("No targets set yet. Configure them in ⚙️ Setup.")

            st.markdown("</div>", unsafe_allow_html=True)

            # ── This Week's Priorities ────────────────────────────────────────
            priorities = r.get("priorities", "").strip()
            st.markdown("""
<div style="background:#0f1a0f;border:1px solid #1a3a1a;border-radius:12px;
            padding:18px 20px;margin-bottom:18px;">
  <p style="color:#4daa4d;font-weight:700;font-size:0.78em;text-transform:uppercase;
            letter-spacing:1px;margin:0 0 10px;">📌 This Week's Priorities</p>
""", unsafe_allow_html=True)
            if priorities:
                for line in priorities.splitlines():
                    if line.strip():
                        st.markdown(
                            f"<p style='margin:4px 0;font-size:0.92em;'>• {line.strip()}</p>",
                            unsafe_allow_html=True,
                        )
            else:
                st.markdown("<p style='color:#556655;font-size:0.88em;'>No priorities set this week.</p>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # ── Weekly Strategy ───────────────────────────────────────────────
            tasks = r.get("tasks", [])
            enabled_tasks = [t for t in tasks if t.get("enabled", True)]

            st.markdown("""
<div style="background:#0f0f1f;border:1px solid #2a2a4a;border-radius:12px;padding:18px 20px;">
  <p style="color:#a07aff;font-weight:700;font-size:0.78em;text-transform:uppercase;
            letter-spacing:1px;margin:0 0 12px;">📋 Weekly Strategy</p>
""", unsafe_allow_html=True)

            if enabled_tasks:
                cats = OrderedDict()
                for t in enabled_tasks:
                    cat = t.get("category", "Other")
                    cats.setdefault(cat, []).append(t)

                for cat, items in cats.items():
                    st.markdown(
                        f"<p style='color:#4da6ff;font-weight:700;font-size:0.8em;"
                        f"text-transform:uppercase;margin:12px 0 4px;'>{cat}</p>",
                        unsafe_allow_html=True,
                    )
                    for t in items:
                        pts = t.get("points", 0)
                        st.markdown(
                            f"<p style='font-size:0.88em;margin:3px 0;'>"
                            f"☐ {t['task']} "
                            f"<span style='color:#556688;'>({pts} pts)</span></p>",
                            unsafe_allow_html=True,
                        )
            else:
                st.markdown("<p style='color:#445;font-size:0.88em;'>No tasks configured.</p>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

            if r.get("folder_url"):
                st.markdown(f"\n📁 [Open coaching folder ↗]({r['folder_url']})")

        # ── RIGHT: Score History ──────────────────────────────────────────────
        with col_right:
            st.markdown("#### 📜 Score History")

            history = r.get("score_history", [])
            if not history:
                st.info("No history yet. Scores are collected each Sunday after the pipeline runs.")
            else:
                # Unique categories from enabled tasks
                all_cats = list(dict.fromkeys(
                    t.get("category", "Other")
                    for t in r.get("tasks", [])
                    if t.get("enabled", True)
                ))

                rows = []
                for entry in reversed(history):
                    row = {
                        "Week":  entry.get("week_label", entry.get("week", "")),
                        "Total": f"{entry.get('percentage', entry.get('score', 0))}%",
                    }
                    cat_scores = entry.get("category_scores", {})
                    for cat in all_cats:
                        val = cat_scores.get(cat)
                        row[cat] = f"{val}%" if val is not None else "—"
                    rows.append(row)

                hist_df = pd.DataFrame(rows)
                st.dataframe(hist_df, use_container_width=True, hide_index=True, height=420)

                # Summary metrics
                if len(history) >= 1:
                    last = history[-1]
                    last_pct = last.get("percentage", last.get("score", 0))
                    st.metric("Last Week", f"{last_pct}%")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: Realtors (management + setup)
# ══════════════════════════════════════════════════════════════════════════════
with tab_realtors:
    from config import load_realtors, save_realtors, init_realtor_tasks, COACHING_CHECKLIST
    from collections import OrderedDict

    realtors = load_realtors()

    st.subheader("👥 Realtors")

    # ── Add new realtor form ──────────────────────────────────────────────────
    with st.expander("➕ Add a new realtor", expanded=len(realtors) == 0):
        with st.form("add_realtor"):
            c1, c2 = st.columns(2)
            new_name  = c1.text_input("Full Name")
            new_email = c2.text_input("Email")
            new_focus = st.text_input(
                "Coaching Focus",
                placeholder="e.g. Lead generation & prospecting",
            )
            submitted = st.form_submit_button("Add Realtor", type="primary")

            if submitted:
                if not new_name or not new_email:
                    st.error("Name and email are required.")
                else:
                    import re, uuid
                    slug = re.sub(r"[^a-z0-9]", "_", new_name.lower())
                    new_realtor = {
                        "id":             f"realtor_{slug}_{uuid.uuid4().hex[:6]}",
                        "name":           new_name.strip(),
                        "email":          new_email.strip().lower(),
                        "coaching_focus": new_focus.strip() or "General coaching",
                        "martin_goals":   "",
                        "priorities":     "",
                        "yearly_goals":   {
                            "conservative_gci": 0,
                            "stretch_gci":      0,
                            "total_deals":      0,
                            "buyer_deals":      0,
                            "seller_deals":     0,
                        },
                        "tasks":          init_realtor_tasks(),
                        "score_history":  [],
                        "folder_id":      "",
                        "folder_url":     "",
                    }
                    realtors.append(new_realtor)
                    save_realtors(realtors)

                    folder_ok = False
                    with st.spinner(f"Creating Drive folder for {new_name}…"):
                        try:
                            from agents.sheets_manager import create_realtor_folder
                            folder_info = create_realtor_folder(new_realtor)
                            realtors[-1]["folder_id"]  = folder_info["folder_id"]
                            realtors[-1]["folder_url"] = folder_info["folder_url"]
                            save_realtors(realtors)
                            folder_ok = True
                        except Exception as e:
                            st.warning(f"Realtor saved, but Drive folder creation failed: {e}")

                    if folder_ok:
                        try:
                            from agents.email_sender import send_welcome_email
                            send_welcome_email(
                                realtors[-1],
                                realtors[-1]["folder_url"],
                                dry_run=dry_run,
                            )
                            st.success(f"✅ {new_name} added — Drive folder created and welcome email sent.")
                        except Exception as e:
                            st.warning(f"Folder created but welcome email failed: {e}")
                            st.success(f"✅ {new_name} added with Drive folder.")
                    else:
                        st.success(f"✅ {new_name} added (no Drive folder yet).")

                    st.rerun()

    # ── Realtor list ──────────────────────────────────────────────────────────
    if not realtors:
        st.info("No realtors yet. Use the form above to add the first one.")
    else:
        if "sheet_links" not in st.session_state:
            st.session_state["sheet_links"] = {}

        for i, r in enumerate(realtors):
            col_info, col_sheet, col_setup, col_edit, col_del = st.columns([4, 2, 1, 1, 1])

            with col_info:
                st.markdown(
                    f"**{r['name']}** &nbsp; `{r['email']}`  \n"
                    f"<span style='color:#7a8aaa;font-size:0.85em;'>{r['coaching_focus']}</span>",
                    unsafe_allow_html=True,
                )
                if r.get("folder_url"):
                    st.markdown(f"📁 [Open coaching folder ↗]({r['folder_url']})")
                link_key = r["id"]
                if link_key in st.session_state["sheet_links"]:
                    info = st.session_state["sheet_links"][link_key]
                    tag  = "♻️ Reused" if info.get("reused") else "✅ Created"
                    st.markdown(f"{tag} &nbsp; [Open sheet in Drive ↗]({info['url']})")

            with col_sheet:
                if st.button("📄 Create Sheet", key=f"sheet_{i}", use_container_width=True,
                             help="Create this week's coaching sheet in the MJ Realty shared drive now."):
                    with st.spinner(f"Creating sheet for {r['name']}…"):
                        try:
                            from agents.sheets_manager import create_weekly_sheet
                            sheet_info = create_weekly_sheet(r)
                            st.session_state["sheet_links"][r["id"]] = sheet_info
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            with col_setup:
                if st.button("⚙️ Setup", key=f"setup_{i}", use_container_width=True):
                    key = f"setup_open_{i}"
                    st.session_state[key] = not st.session_state.get(key, False)
                    st.rerun()

            with col_edit:
                if st.button("Edit", key=f"edit_{i}", use_container_width=True):
                    st.session_state[f"editing_{i}"] = True

            with col_del:
                if st.button("Remove", key=f"del_{i}", use_container_width=True):
                    realtors.pop(i)
                    save_realtors(realtors)
                    st.rerun()

            # ── Inline edit form ──────────────────────────────────────────────
            if st.session_state.get(f"editing_{i}"):
                with st.form(f"edit_form_{i}"):
                    ec1, ec2 = st.columns(2)
                    upd_name  = ec1.text_input("Name",  value=r["name"])
                    upd_email = ec2.text_input("Email", value=r["email"])
                    upd_focus = st.text_input("Coaching Focus", value=r["coaching_focus"])
                    s1, s2    = st.columns(2)
                    if s1.form_submit_button("Save", type="primary"):
                        realtors[i].update({
                            "name":           upd_name.strip(),
                            "email":          upd_email.strip().lower(),
                            "coaching_focus": upd_focus.strip(),
                        })
                        save_realtors(realtors)
                        del st.session_state[f"editing_{i}"]
                        st.rerun()
                    if s2.form_submit_button("Cancel"):
                        del st.session_state[f"editing_{i}"]
                        st.rerun()

            # ══════════════════════════════════════════════════════════════════
            # ⚙️ Setup Panel
            # ══════════════════════════════════════════════════════════════════
            if st.session_state.get(f"setup_open_{i}", False):
                with st.container(border=True):
                    st.markdown(f"#### ⚙️ Coaching Setup — {r['name']}")

                    # ── 1. Yearly Goals ───────────────────────────────────────
                    st.markdown("**🎯 Yearly Goals**")
                    goals = r.get("yearly_goals", {})

                    with st.form(f"yearly_goals_{i}"):
                        yg1, yg2 = st.columns(2)
                        conservative_gci = yg1.number_input(
                            "Conservative GCI ($)",
                            min_value=0, step=10000,
                            value=int(goals.get("conservative_gci", 0)),
                        )
                        stretch_gci = yg2.number_input(
                            "Stretch GCI ($)",
                            min_value=0, step=10000,
                            value=int(goals.get("stretch_gci", 0)),
                        )
                        yg3, yg4, yg5 = st.columns(3)
                        total_deals  = yg3.number_input(
                            "Total Deals", min_value=0,
                            value=int(goals.get("total_deals", 0)),
                        )
                        buyer_deals  = yg4.number_input(
                            "Buyer Deals", min_value=0,
                            value=int(goals.get("buyer_deals", 0)),
                        )
                        seller_deals = yg5.number_input(
                            "Seller Deals", min_value=0,
                            value=int(goals.get("seller_deals", 0)),
                        )
                        if st.form_submit_button("💾 Save Yearly Goals", type="primary"):
                            realtors[i]["yearly_goals"] = {
                                "conservative_gci": int(conservative_gci),
                                "stretch_gci":      int(stretch_gci),
                                "total_deals":      int(total_deals),
                                "buyer_deals":      int(buyer_deals),
                                "seller_deals":     int(seller_deals),
                            }
                            save_realtors(realtors)
                            st.success("Yearly goals saved.")
                            st.rerun()

                    st.markdown("---")

                    # ── 2. Martin's Goals ─────────────────────────────────────
                    st.markdown("**📌 Martin's Goals for This Week**")
                    new_martin_goals = st.text_area(
                        label="goals",
                        value=r.get("martin_goals", ""),
                        height=100,
                        key=f"martin_goals_{i}",
                        label_visibility="collapsed",
                        placeholder="Type your goals, coaching focus, or message for this realtor…",
                    )
                    if st.button("💾 Save Goals", key=f"save_goals_{i}"):
                        realtors[i]["martin_goals"] = new_martin_goals.strip()
                        save_realtors(realtors)
                        st.success("Saved.")
                        st.rerun()

                    st.markdown("---")

                    # ── 3. Priorities ─────────────────────────────────────────
                    st.markdown("**📝 This Week's Priorities**")
                    st.caption("Shown on the realtor's sheet. One priority per line.")
                    new_priorities = st.text_area(
                        label="priorities",
                        value=r.get("priorities", ""),
                        height=120,
                        key=f"priorities_{i}",
                        label_visibility="collapsed",
                        placeholder="e.g.\nClose the Henderson deal\nCall all warm leads from last month\nPost 5 times on Instagram",
                    )
                    if st.button("💾 Save Priorities", key=f"save_priorities_{i}"):
                        realtors[i]["priorities"] = new_priorities.strip()
                        save_realtors(realtors)
                        st.success("Priorities saved.")
                        st.rerun()

                    st.markdown("---")

                    # ── 4. Weekly Strategy (tasks) ────────────────────────────
                    st.markdown("**📋 Weekly Strategy**")
                    st.caption("Toggle tasks on/off, adjust points, or add custom tasks. Only enabled tasks appear on the sheet.")

                    if "tasks" not in realtors[i] or not realtors[i]["tasks"]:
                        realtors[i]["tasks"] = init_realtor_tasks()
                        save_realtors(realtors)
                        st.rerun()

                    tasks = realtors[i].get("tasks", [])
                    tasks_changed = False

                    cats = OrderedDict()
                    for idx, t in enumerate(tasks):
                        cat = t.get("category", "Other")
                        cats.setdefault(cat, []).append((idx, t))

                    for cat, items in cats.items():
                        st.markdown(
                            f"<p style='color:#4da6ff;font-weight:700;font-size:0.88em;"
                            f"text-transform:uppercase;margin:12px 0 4px;'>{cat}</p>",
                            unsafe_allow_html=True,
                        )
                        for idx, t in items:
                            col_toggle, col_task, col_pts, col_rm = st.columns([0.5, 5, 1.2, 0.7])

                            enabled = col_toggle.checkbox(
                                "", value=t.get("enabled", True),
                                key=f"task_en_{i}_{idx}",
                                label_visibility="collapsed",
                            )
                            if enabled != t.get("enabled", True):
                                realtors[i]["tasks"][idx]["enabled"] = enabled
                                tasks_changed = True

                            style = "color:#666;" if not t.get("enabled", True) else ""
                            col_task.markdown(
                                f"<span style='font-size:0.9em;{style}'>{t['task']}</span>",
                                unsafe_allow_html=True,
                            )

                            new_pts = col_pts.number_input(
                                "pts", min_value=1, max_value=50,
                                value=int(t.get("points", 5)),
                                key=f"task_pts_{i}_{idx}",
                                label_visibility="collapsed",
                            )
                            if new_pts != t.get("points"):
                                realtors[i]["tasks"][idx]["points"] = int(new_pts)
                                tasks_changed = True

                            if t.get("is_custom", False):
                                if col_rm.button("✕", key=f"task_rm_{i}_{idx}"):
                                    realtors[i]["tasks"].pop(idx)
                                    save_realtors(realtors)
                                    st.rerun()

                    if tasks_changed:
                        save_realtors(realtors)

                    enabled_pts = sum(t["points"] for t in tasks if t.get("enabled", True))
                    st.caption(f"Total points for enabled tasks: **{enabled_pts} pts**")

                    col_save, col_reset = st.columns(2)
                    if col_save.button("💾 Save All Task Changes", key=f"save_tasks_{i}", type="primary"):
                        save_realtors(realtors)
                        st.success("Tasks saved.")
                        st.rerun()
                    if col_reset.button("↺ Reset to Defaults", key=f"reset_tasks_{i}"):
                        realtors[i]["tasks"] = init_realtor_tasks()
                        save_realtors(realtors)
                        st.rerun()

                    st.markdown("---")

                    # ── Add custom task ───────────────────────────────────────
                    st.markdown("**➕ Add Custom Task**")
                    with st.form(f"add_ct_{i}"):
                        ct1, ct2, ct3 = st.columns([4, 2, 1])
                        new_ct_task = ct1.text_input(
                            "Task",
                            placeholder="e.g. Send video message to 3 leads",
                            label_visibility="collapsed",
                        )
                        from config import COACHING_CHECKLIST as _cl
                        _cats = list(dict.fromkeys(t["category"] for t in _cl)) + ["Custom"]
                        new_ct_cat = ct2.selectbox(
                            "Category", options=_cats, index=len(_cats) - 1,
                            key=f"ct_cat_{i}", label_visibility="collapsed",
                        )
                        new_ct_pts = ct3.number_input(
                            "Points", min_value=1, max_value=50, value=5,
                            label_visibility="collapsed",
                        )
                        if st.form_submit_button("➕ Add Task", use_container_width=True):
                            if new_ct_task.strip():
                                realtors[i]["tasks"].append({
                                    "category":  new_ct_cat.strip() or "Custom",
                                    "task":      new_ct_task.strip(),
                                    "points":    int(new_ct_pts),
                                    "type":      "checkbox",
                                    "enabled":   True,
                                    "is_custom": True,
                                })
                                save_realtors(realtors)
                                st.success(f"Added: {new_ct_task.strip()}")
                                st.rerun()
                            else:
                                st.warning("Task text cannot be empty.")

            st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Sunday reminder result
# ══════════════════════════════════════════════════════════════════════════════
with tab_sunday:
    result = st.session_state["sunday_result"]
    if not result:
        st.info("Click 'Send Sunday Reminders' to remind realtors their sheet is due tonight.")
    else:
        st.subheader(f"📨 Sunday Reminders — {result.get('week_label', '')}")

        reminded = result.get("reminded", [])
        if reminded:
            st.markdown(f"**{len(reminded)} reminder{'s' if len(reminded) != 1 else ''} sent:**")
            remind_df = pd.DataFrame([{
                "Realtor": r.get("realtor_name", ""),
                "Email":   r.get("to", ""),
                "Status":  r.get("status", ""),
            } for r in reminded])
            st.dataframe(remind_df, use_container_width=True, hide_index=True)
        else:
            if result.get("errors"):
                st.warning("No reminders were sent. Check errors below.")
            else:
                st.info("No sheets found for this week — run the Monday pipeline first so sheets exist to remind about.")

        if result.get("errors"):
            st.error(f"Errors: {result['errors']}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4: Monday report
# ══════════════════════════════════════════════════════════════════════════════
with tab_monday:
    result = st.session_state["monday_result"]
    if not result:
        st.info("Run the Monday pipeline to see results here.")
    else:
        report = result.get("report") or result
        st.subheader(f"📊 Report — {result.get('week_label', report.get('week_label', ''))}")

        m1, m2, m3 = st.columns(3)
        m1.metric("Realtors",  report["total_realtors"])
        m2.metric("Submitted", report["submitted"])
        submitted = report["submitted"]
        avg = (sum(e["percentage"] for e in report["entries"] if e["uploaded"])
               // max(submitted, 1))
        m3.metric("Avg Score", f"{avg}%")

        st.markdown("---")

        for entry in report["entries"]:
            from config import score_label
            label, color = score_label(entry["percentage"])
            icon = "✅" if entry["uploaded"] else "❌"

            with st.expander(f"{icon} {entry['realtor_name']} — {entry['percentage']}% ({label})"):
                if not entry["uploaded"]:
                    st.warning("Did not upload their sheet this week.")
                    continue

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Completed:**")
                    for t in entry["completed"]:
                        st.markdown(f"✅ {t}")
                with c2:
                    st.markdown("**Not completed:**")
                    for t in entry["incomplete"]:
                        st.markdown(f"☐ {t}")

                if entry["activity_totals"]:
                    st.markdown("**Weekly Activity Totals:**")
                    act_df = pd.DataFrame([{"Metric": k, "Total": v}
                                           for k, v in entry["activity_totals"].items()])
                    st.dataframe(act_df, use_container_width=True, hide_index=True)

                if entry["note_to_martin"]:
                    st.info(f"**Note to Martin:** {entry['note_to_martin']}")

                st.markdown(f"[Open Sheet]({entry['sheet_url']})")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 5: Weekly Strategy template
# ══════════════════════════════════════════════════════════════════════════════
with tab_checklist:
    from config import COACHING_CHECKLIST, SCORE_THRESHOLDS
    st.subheader("📋 Weekly Strategy Template")
    st.caption(f"These tasks appear on every realtor's sheet by default. Total: {sum(i['points'] for i in COACHING_CHECKLIST)} pts")

    checklist_df = pd.DataFrame([{
        "Category": i["category"],
        "Task":     i["task"],
        "Points":   i["points"],
    } for i in COACHING_CHECKLIST])
    st.dataframe(checklist_df, use_container_width=True, hide_index=True, height=420)

    st.markdown("---")
    st.subheader("🏆 Score Ratings")
    threshold_df = pd.DataFrame([{
        "Rating": label,
        "Min %":  lo,
        "Max %":  hi,
    } for label, (lo, hi, _) in SCORE_THRESHOLDS.items()])
    st.dataframe(threshold_df, use_container_width=True, hide_index=True)
