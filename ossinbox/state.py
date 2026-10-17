"""The actions both UIs share, so the web page and the terminal UI behave the same."""

import time

from . import db, forgejo, notes, sync

# The poller writes a heartbeat each round. Older than this means it is not running.
HEARTBEAT_MAX_AGE = 180


def _hours(value):
    """'' or None clears the override. 0 turns reminders off."""
    if value in (None, ""):
        return None
    hours = float(value)
    if hours < 0:
        raise ValueError("hours must be 0 or more")
    return hours


def repo_name(conn, text):
    """Turn "owner/repo" or a repo URL into the stored name.

    GitHub: "owner/repo". Codeberg: "codeberg.org/owner/repo".
    """
    name = text.strip().removeprefix("https://").removeprefix("http://").strip("/")
    name = name.removesuffix(".git").removeprefix("github.com/")
    host = forgejo.host(db.get_setting(conn, "forgejo_url"))
    parts = name.split("/")
    if len(parts) == 3 and parts[0] == host and all(parts):
        return name
    if len(parts) == 2 and all(parts):
        return name
    raise ValueError(f"use the form owner/repo, or a URL on github.com or {host}")


def apply(conn, action, body):
    """Run one UI action. Raise KeyError or ValueError on bad input."""
    if action == "items/done":
        db.set_done(conn, body["key"], body["category"], bool(body["done"]))
    elif action == "items/all-done":
        db.mark_all_done(conn, body["category"])
    elif action == "items/priority":
        db.set_priority(conn, body["key"], body["category"], bool(body["high"]))
    elif action == "items/move":
        db.move_item(conn, body["key"], body["category"], body["to"])
    elif action == "items/remind":
        db.set_remind(conn, body["key"], body["category"], _hours(body.get("hours")))
    elif action == "items/stall":
        db.set_stall_days(conn, body["key"], _hours(body.get("days")))
        sync.refresh_stalled(conn)
    elif action == "items/note":
        item = conn.execute("SELECT * FROM items WHERE key = ? LIMIT 1",
                            (body["key"],)).fetchone()
        if item is None:
            raise KeyError(body["key"])
        notes.save(db.get_setting(conn, "notes_file"), item, body.get("body"))
    elif action == "repos/watch":
        db.set_watched(conn, body["full_name"], bool(body["watched"]))
    elif action == "repos/add":
        db.add_repo(conn, repo_name(conn, body["full_name"]), watched=True)
    elif action == "forgejo/token":
        db.set_token(body.get("token"))
    elif action == "settings":
        for key, value in body.items():
            db.set_setting(conn, key, value)
        sync.refresh_stalled(conn)
    else:
        raise KeyError(f"unknown action {action}")


def status(conn):
    beat = db.get_meta(conn, "heartbeat")
    running = bool(beat) and time.time() - float(beat) < HEARTBEAT_MAX_AGE
    return {
        "login": db.get_meta(conn, "login"),
        "forgejo_login": db.get_meta(conn, "forgejo_login") if db.get_token() else None,
        # Only whether a token exists. The token itself never leaves the file.
        "forgejo_token": bool(db.get_token()),
        "last_sync": db.get_meta(conn, "last_sync"),
        "last_error": db.get_meta(conn, "last_error") or "",
        "poller_running": running,
        "counts": db.counts(conn),
        "settings": {k: db.get_setting(conn, k) for k in db.DEFAULT_SETTINGS},
        "defaults": db.DEFAULT_SETTINGS,
        "watched": len(db.watched_repos(conn)),
        "rate": sync.rate_status(conn),
        "estimate_per_hour": sync.estimate_per_hour(conn),
        "last_sync_cost": db.get_meta(conn, "last_sync_cost"),
    }
