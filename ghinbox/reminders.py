"""Desktop pop-ups for new action items, to-dos, reminders, and stalled work."""

import time
from datetime import datetime, timedelta, timezone

from . import db, osdeps

# More pop-ups than this in one round become one summary pop-up.
MAX_POPUPS = 5
# GNOME does not show every banner when pop-ups come too fast.
POPUP_GAP_SECONDS = 2

LABELS = {
    "review_requested": "Review requested",
    "mention": "You were mentioned",
    "todo": "Your to-do",
    "team_mention": "Your team was mentioned",
    "assign": "You were assigned",
}

# An emoji at the start of the title shows what the pop-up is about.
ICONS = {
    "review_requested": "🔍",
    "mention": "💬",
    "todo": "✅",
    "team_mention": "👥",
    "assign": "📌",
    "waiting": "⏳",
    "stalled": "💤",
    "summary": "📬",
    "rate": "⚠️",
}


def due(conn):
    """Return the open items that need a pop-up now."""
    default_hours = db.get_setting(conn, "default_remind_hours", float)
    now = datetime.now(timezone.utc)
    out = []
    for row in conn.execute(
            f"SELECT *, {db.SHOWN} AS tab FROM items WHERE done = 0 AND "
            f"({db.SHOWN} IN ('action', 'todo') OR ({db.SHOWN} = 'mine' AND category = 'mine' "
            "AND (stalled = 1 OR waiting_for IS NOT NULL)))"):
        last = db.parse_iso(row["last_notified"])
        if last is None:
            out.append(row)
            continue
        hours = row["remind_hours"]
        if hours is None:
            # A waiting review repeats like an action item. A stalled item does not.
            hours = default_hours if row["tab"] in ("action", "todo") or row["waiting_for"] else 0
        if hours > 0 and now - last >= timedelta(hours=hours):
            out.append(row)
    return out


def _message(row):
    ref = f"{row['repo']}#{row['number']}" if row["number"] else row["repo"]
    if row["tab"] == "mine" and row["waiting_for"]:
        icon = ICONS["waiting"]
        title = "Review overdue: @" + row["waiting_for"].replace(", ", ", @")
    elif row["tab"] == "mine":
        icon = ICONS["stalled"]
        title = "Stalled: no activity on your " + ("PR" if row["kind"] == "pr" else "issue")
    elif row["tab"] == "todo":
        icon = ICONS["todo"]
        title = LABELS["todo"]
    else:
        icon = ICONS.get(row["reason"], "🔔")
        title = LABELS.get(row["reason"], "Needs your action")
    if row["notify_count"] > 0:
        title = f"Reminder {row['notify_count']}: {title}"
    return f"{icon} {title}", f"{ref}\n{row['title']}"


def rate_warning(conn):
    """Send one pop-up for each rate-limit window in which few requests are left."""
    from . import sync
    rate = sync.rate_status(conn)
    if rate["level"] not in ("low", "paused") or db.get_meta(conn, "rate_warned") == str(rate["reset"]):
        return
    db.set_meta(conn, "rate_warned", str(rate["reset"]))
    if db.get_setting(conn, "notify", float):
        osdeps.notify(
            f"{ICONS['rate']} gh-inbox: few API requests left",
            f"{rate['remaining']} of {rate['limit']} left until {rate['reset_clock']}. "
            "Watch fewer repos or sync less often.", urgent=True)


def run(conn):
    """Send every due pop-up and record it. Return the number of items handled."""
    rows = due(conn)
    if not rows:
        return 0
    if db.get_setting(conn, "notify", float):
        if len(rows) > MAX_POPUPS:
            osdeps.notify(f"{ICONS['summary']} gh-inbox: {len(rows)} items need you",
                          "Open the app to see them.", urgent=any(r["notify_count"] for r in rows))
        else:
            for i, row in enumerate(rows):
                if i:
                    time.sleep(POPUP_GAP_SECONDS)
                title, body = _message(row)
                osdeps.notify(title, body, urgent=row["notify_count"] > 0)
    now = db.now_iso()
    conn.executemany(
        "UPDATE items SET last_notified = ?, notify_count = notify_count + 1 "
        "WHERE key = ? AND category = ?",
        [(now, r["key"], r["category"]) for r in rows])
    conn.commit()
    return len(rows)
