"""The actions both UIs share, so the web page and the terminal UI behave the same."""

import time

from ..core import items
from ..providers import registry
from ..providers.forgejo.client import TOKEN_NAME
from ..storage import db, notes, secrets

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
    return registry.parse_repo(conn, text)


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
        items.refresh_stalled(conn)
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
        secrets.set_token(TOKEN_NAME, body.get("token"))
    elif action == "settings":
        for key, value in body.items():
            db.set_setting(conn, key, value)
        items.refresh_stalled(conn)
    else:
        raise KeyError(f"unknown action {action}")


def status(conn):
    beat = db.get_meta(conn, "heartbeat")
    running = bool(beat) and time.time() - float(beat) < HEARTBEAT_MAX_AGE
    out = {
        "last_sync": db.get_meta(conn, "last_sync"),
        "last_error": db.get_meta(conn, "last_error") or "",
        "poller_running": running,
        "counts": db.counts(conn),
        "settings": {k: db.get_setting(conn, k) for k in db.DEFAULT_SETTINGS},
        "defaults": db.DEFAULT_SETTINGS,
        "watched": len(db.watched_repos(conn)),
    }
    for provider in registry.PROVIDERS:
        out.update(provider.status(conn))
    return out
