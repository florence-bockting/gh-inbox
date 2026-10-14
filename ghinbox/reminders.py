"""Desktop pop-ups for new action items, reminders, and stalled work."""

from datetime import datetime, timedelta, timezone

from . import db, osdeps

# More pop-ups than this in one round become one summary pop-up.
MAX_POPUPS = 5

LABELS = {
    "review_requested": "Review requested",
    "mention": "You were mentioned",
    "team_mention": "Your team was mentioned",
    "assign": "You were assigned",
}


def due(conn):
    """Return the open items that need a pop-up now."""
    default_hours = db.get_setting(conn, "default_remind_hours", float)
    now = datetime.now(timezone.utc)
    out = []
    for row in conn.execute(
            "SELECT * FROM items WHERE done = 0 AND "
            "(category = 'action' OR (category = 'mine' AND stalled = 1))"):
        last = db.parse_iso(row["last_notified"])
        if last is None:
            out.append(row)
            continue
        hours = row["remind_hours"]
        if hours is None:
            hours = default_hours if row["category"] == "action" else 0
        if hours > 0 and now - last >= timedelta(hours=hours):
            out.append(row)
    return out


def _message(row):
    ref = f"{row['repo']}#{row['number']}" if row["number"] else row["repo"]
    if row["category"] == "mine":
        title = "Stalled: no activity on your " + ("PR" if row["kind"] == "pr" else "issue")
    else:
        title = LABELS.get(row["reason"], "Needs your action")
    if row["notify_count"] > 0:
        title = f"Reminder {row['notify_count']}: {title}"
    return title, f"{ref}\n{row['title']}"


def run(conn):
    """Send every due pop-up and record it. Return the number of items handled."""
    rows = due(conn)
    if not rows:
        return 0
    if db.get_setting(conn, "notify", float):
        if len(rows) > MAX_POPUPS:
            osdeps.notify(f"GitHub Inbox: {len(rows)} items need you",
                          "Open the app to see them.", urgent=any(r["notify_count"] for r in rows))
        else:
            for row in rows:
                title, body = _message(row)
                osdeps.notify(title, body, urgent=row["notify_count"] > 0)
    now = db.now_iso()
    conn.executemany(
        "UPDATE items SET last_notified = ?, notify_count = notify_count + 1 "
        "WHERE key = ? AND category = ?",
        [(now, r["key"], r["category"]) for r in rows])
    conn.commit()
    return len(rows)
