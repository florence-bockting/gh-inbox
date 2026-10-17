"""Insert, reopen and close items. Each forge sync calls these, so all forges behave the same."""

from datetime import timedelta

from ..storage import db
from .timeutil import later, now_iso, parse_iso, utcnow

ACTION_PRIORITY = {"review_requested": 0, "mention": 1, "team_mention": 2, "assign": 3}


def upsert(conn, item, reopen=True, bump=True):
    """Insert or update one item. Only the forge fields change; your own settings stay.

    Return "new", "reopened", "newer" (newer event) or "updated".
    A done item opens again when a newer event arrives and `reopen` is true.
    With `bump` false, a newer event does not move `event_at`.
    """
    row = conn.execute(
        "SELECT * FROM items WHERE key = ? AND category = ?",
        (item["key"], item["category"])).fetchone()
    now = now_iso()
    if row is None:
        remind = None
        if item["category"] in ("action", "todo"):
            remind = db.get_setting(conn, "default_remind_hours", float)
        conn.execute(
            "INSERT INTO items (key, category, repo, number, kind, title, url, author, state, "
            "reason, event_at, updated_at, first_seen, remind_hours) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item["key"], item["category"], item["repo"], item.get("number"), item.get("kind"),
             item.get("title"), item.get("url"), item.get("author"), item.get("state"),
             item.get("reason"), item.get("event_at") or now, item.get("updated_at"), now,
             remind))
        return "new"

    newer = later(item.get("event_at"), row["event_at"])
    reason = row["reason"]
    if newer:
        reason = item.get("reason") or reason
    elif (item["category"] == "action" and item.get("reason") in ACTION_PRIORITY
          and ACTION_PRIORITY[item["reason"]] < ACTION_PRIORITY.get(reason, 99)):
        reason = item["reason"]
    event_at = item["event_at"] if newer and bump else row["event_at"]
    conn.execute(
        "UPDATE items SET title = coalesce(?, title), url = coalesce(?, url), "
        "author = coalesce(?, author), state = coalesce(?, state), "
        "updated_at = coalesce(?, updated_at), reason = ?, event_at = ? "
        "WHERE key = ? AND category = ?",
        (item.get("title"), item.get("url"), item.get("author"), item.get("state"),
         item.get("updated_at"), reason, event_at, item["key"], item["category"]))
    if row["done"] and newer and reopen and later(item["event_at"], row["done_at"]):
        reopen_item(conn, item["key"], item["category"])
        return "reopened"
    return "newer" if newer else "updated"


def reopen_item(conn, key, category):
    conn.execute(
        "UPDATE items SET done = 0, done_at = NULL, auto_done = 0, last_notified = NULL, "
        "notify_count = 0 WHERE key = ? AND category = ?", (key, category))


def auto_done(conn, key, category, state=None):
    conn.execute(
        "UPDATE items SET done = 1, done_at = ?, auto_done = 1, state = coalesce(?, state) "
        "WHERE key = ? AND category = ? AND done = 0",
        (now_iso(), state, key, category))


def refresh_stalled(conn):
    """Flag your items with no activity for longer than their stall time."""
    default_days = db.get_setting(conn, "stall_days", float)
    now = utcnow()
    for row in conn.execute(
            "SELECT key, updated_at, stall_days, stalled FROM items "
            "WHERE category = 'mine' AND done = 0").fetchall():
        days = row["stall_days"] if row["stall_days"] is not None else default_days
        idle = now - parse_iso(row["updated_at"])
        stalled = int(days > 0 and idle >= timedelta(days=days))
        if stalled != row["stalled"]:
            conn.execute(
                "UPDATE items SET stalled = ?, last_notified = NULL, notify_count = 0 "
                "WHERE key = ? AND category = 'mine'", (stalled, row["key"]))
    conn.commit()
