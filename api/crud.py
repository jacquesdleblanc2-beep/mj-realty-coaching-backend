from .db import supabase


# ── Coaches ────────────────────────────────────────────────────────────────────

def get_all_coaches() -> list[dict]:
    return supabase.table("coaches").select("*").execute().data


def get_coach_by_id(coach_id: str) -> dict | None:
    res = supabase.table("coaches").select("*").eq("id", coach_id).execute()
    return res.data[0] if res.data else None


def get_coach_by_email(email: str) -> dict | None:
    res = supabase.table("coaches").select("*").ilike("email", email).execute()
    return res.data[0] if res.data else None


def create_coach(coach_id: str, name: str, email: str) -> dict:
    return supabase.table("coaches").insert(
        {"id": coach_id, "name": name, "email": email}
    ).execute().data[0]


def update_coach(coach_id: str, data: dict) -> dict:
    return supabase.table("coaches").update(data).eq("id", coach_id).execute().data[0]


def delete_coach(coach_id: str) -> None:
    supabase.table("realtors").update({"coach_id": None}).eq("coach_id", coach_id).execute()
    supabase.table("coaches").delete().eq("id", coach_id).execute()


def get_coaches_with_realtors() -> list[dict]:
    coaches = get_all_coaches()
    for c in coaches:
        c["realtors"] = get_realtors_by_coach(c["id"])
    return coaches


# ── Realtors ───────────────────────────────────────────────────────────────────

def get_all_realtors() -> list[dict]:
    return supabase.table("realtors").select("*").execute().data


def get_realtor_by_id(realtor_id: str) -> dict | None:
    res = supabase.table("realtors").select("*").eq("id", realtor_id).execute()
    return res.data[0] if res.data else None


def get_realtor_by_email(email: str) -> dict | None:
    res = supabase.table("realtors").select("*").ilike("email", email).execute()
    return res.data[0] if res.data else None


def get_realtors_by_coach(coach_id: str) -> list[dict]:
    return supabase.table("realtors").select("*").eq("coach_id", coach_id).execute().data


def assign_realtor_to_coach(realtor_id: str, coach_id: str) -> dict:
    return supabase.table("realtors").update({"coach_id": coach_id}).eq("id", realtor_id).execute().data[0]


def create_realtor(
    realtor_id: str,
    name: str,
    email: str,
    coach_id: str | None = None,
    coaching_focus: str = "General coaching",
) -> dict:
    return supabase.table("realtors").insert({
        "id":             realtor_id,
        "name":           name,
        "email":          email,
        "coach_id":       coach_id,
        "coaching_focus": coaching_focus,
        "yearly_goals":   {},
        "tasks":          [],
        "score_history":  [],
    }).execute().data[0]


def update_realtor(realtor_id: str, data: dict) -> dict:
    return supabase.table("realtors").update(data).eq("id", realtor_id).execute().data[0]


def delete_realtor(realtor_id: str) -> None:
    supabase.table("realtors").delete().eq("id", realtor_id).execute()


# ── Weekly progress ────────────────────────────────────────────────────────────

def get_progress(realtor_id: str, week_label: str) -> dict | None:
    res = (
        supabase.table("weekly_progress")
        .select("*")
        .eq("realtor_id", realtor_id)
        .eq("week_label", week_label)
        .execute()
    )
    return res.data[0] if res.data else None


def get_all_progress(realtor_id: str) -> list[dict]:
    return (
        supabase.table("weekly_progress")
        .select("*")
        .eq("realtor_id", realtor_id)
        .order("week_label")
        .execute()
        .data
    )


def upsert_progress(realtor_id: str, week_label: str, data: dict) -> dict:
    return (
        supabase.table("weekly_progress")
        .upsert(
            {"realtor_id": realtor_id, "week_label": week_label, **data},
            on_conflict="realtor_id,week_label",
        )
        .execute()
        .data[0]
    )


# ── Send log ───────────────────────────────────────────────────────────────────

def append_log(
    event: str,
    week_label: str | None = None,
    dry_run: bool = False,
    details: dict | None = None,
) -> None:
    supabase.table("send_log").insert({
        "event":      event,
        "week_label": week_label,
        "dry_run":    dry_run,
        "details":    details or {},
    }).execute()


def get_log_by_week_event(week_label: str, event: str) -> list[dict]:
    return (
        supabase.table("send_log")
        .select("*")
        .eq("week_label", week_label)
        .eq("event", event)
        .execute()
        .data
    )


def get_recent_log(limit: int = 20) -> list[dict]:
    return (
        supabase.table("send_log")
        .select("*")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
        .data
    )
