"""The GitHub rate limit: the stored state, the level, and the cost estimate."""

import json
import time
from datetime import datetime

from ...storage import db
from . import client

# Below this share of the hourly limit, the sync waits for the reset.
PAUSE_SHARE = 0.10
# Below this share, the UIs show a warning and the daemon sends one pop-up.
WARN_SHARE = 0.20


def store_rate(conn):
    rate = dict(client.RATE)
    if rate:
        db.set_meta(conn, "rate", json.dumps(rate))
    return rate or None


def clock(epoch):
    return datetime.fromtimestamp(epoch).strftime("%H:%M")


def rate_status(conn):
    """Return the stored rate limit with a level: ok, low or paused."""
    rate = json.loads(db.get_meta(conn, "rate") or "{}")
    if not rate:
        return {"level": "unknown"}
    if time.time() >= rate["reset"]:
        rate["remaining"] = rate["limit"]  # the window reset since the last request
    share = rate["remaining"] / rate["limit"]
    rate["level"] = "paused" if share < PAUSE_SHARE else "low" if share < WARN_SHARE else "ok"
    rate["reset_clock"] = clock(rate["reset"])
    return rate


def estimate_per_hour(conn):
    """Most requests each hour, if no ETag answer is 304."""
    minutes = db.get_setting(conn, "poll_minutes", float)
    open_checks = conn.execute(
        "SELECT count(*) FROM items WHERE done = 0 AND (category = 'todo' OR "
        "(category = 'action' AND reason IN ('mention', 'team_mention', 'assign')))"
        ).fetchone()[0]
    open_prs = conn.execute(
        "SELECT count(*) FROM items WHERE category = 'mine' AND kind = 'pr' AND done = 0"
        ).fetchone()[0]
    per_sync = 6 + len(db.watched_repos(conn)) + open_checks + open_prs
    return round(per_sync * 60 / max(minutes, 1))
