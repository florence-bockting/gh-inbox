"""SQLite state: watched repos, items per tab, settings."""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("GH_INBOX_DIR", Path.home() / ".local/share/gh-inbox"))
DB_PATH = DATA_DIR / "state.db"

DEFAULT_SETTINGS = {
    "poll_minutes": "5",
    "default_remind_hours": "24",
    "stall_days": "7",
    "notify": "1",
    "new_item_days": "7",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    full_name   TEXT PRIMARY KEY,
    watched     INTEGER NOT NULL DEFAULT 0,
    watch_since TEXT,
    source      TEXT
);
CREATE TABLE IF NOT EXISTS items (
    key           TEXT NOT NULL,
    category      TEXT NOT NULL,      -- action | watch | mine
    repo          TEXT NOT NULL,
    number        INTEGER,
    kind          TEXT,               -- pr | issue | other
    title         TEXT,
    url           TEXT,
    author        TEXT,
    state         TEXT,
    reason        TEXT,
    event_at      TEXT,               -- time of the event that put the item here
    updated_at    TEXT,               -- last update on GitHub
    first_seen    TEXT,
    done          INTEGER NOT NULL DEFAULT 0,
    done_at       TEXT,
    auto_done     INTEGER NOT NULL DEFAULT 0,
    remind_hours  REAL,
    last_notified TEXT,
    notify_count  INTEGER NOT NULL DEFAULT 0,
    stall_days    REAL,
    stalled       INTEGER NOT NULL DEFAULT 0,
    activity      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, category)
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    return datetime.fromisoformat(value) if value else None


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        DEFAULT_SETTINGS.items(),
    )
    conn.commit()
    return conn


# ---- settings ---------------------------------------------------------------

def get_settings(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}


def get_setting(conn, key, cast=str):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return cast(row["value"] if row else DEFAULT_SETTINGS[key])


def set_setting(conn, key, value):
    if key not in DEFAULT_SETTINGS:
        raise KeyError(key)
    float(value)  # every setting is numeric
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


# ---- repos ------------------------------------------------------------------

def list_repos(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM repos ORDER BY watched DESC, lower(full_name)")]


def watched_repos(conn):
    return {r["full_name"] for r in conn.execute("SELECT full_name FROM repos WHERE watched = 1")}


def add_repo(conn, full_name, source="manual", watched=False):
    conn.execute(
        "INSERT OR IGNORE INTO repos (full_name, source) VALUES (?, ?)", (full_name, source))
    if watched:
        set_watched(conn, full_name, True)
    conn.commit()


def set_watched(conn, full_name, watched):
    conn.execute(
        "UPDATE repos SET watched = ?, watch_since = CASE WHEN ? THEN coalesce(watch_since, ?) "
        "ELSE NULL END WHERE full_name = ?",
        (int(watched), int(watched), now_iso(), full_name))
    if not watched:
        conn.execute(
            "DELETE FROM items WHERE repo = ? AND category IN ('action', 'watch')", (full_name,))
    conn.commit()


# ---- items ------------------------------------------------------------------

def list_items(conn, category, show_done=False):
    sql = "SELECT * FROM items WHERE category = ?"
    if not show_done:
        sql += " AND done = 0"
    if category == "watch":
        # An item that needs your action shows only in the Action tab.
        sql += (" AND NOT EXISTS (SELECT 1 FROM items a WHERE a.key = items.key"
                " AND a.category = 'action' AND a.done = 0)")
    sql += " ORDER BY stalled DESC, coalesce(event_at, updated_at) DESC"
    return [dict(r) for r in conn.execute(sql, (category,))]


def counts(conn):
    rows = conn.execute(
        "SELECT category, count(*) AS n FROM items WHERE done = 0 GROUP BY category")
    return {r["category"]: r["n"] for r in rows}


def set_done(conn, key, category, done):
    conn.execute(
        "UPDATE items SET done = ?, done_at = ?, auto_done = 0 WHERE key = ? AND category = ?",
        (int(done), now_iso() if done else None, key, category))
    conn.commit()


def mark_all_done(conn, category):
    conn.execute(
        "UPDATE items SET done = 1, done_at = ?, auto_done = 0 WHERE category = ? AND done = 0",
        (now_iso(), category))
    conn.commit()


def set_remind(conn, key, category, hours):
    """hours = 0 turns reminders off for this item; None uses no override."""
    conn.execute(
        "UPDATE items SET remind_hours = ? WHERE key = ? AND category = ?",
        (hours, key, category))
    conn.commit()


def set_stall_days(conn, key, days):
    """days = None uses the global stall_days setting."""
    conn.execute(
        "UPDATE items SET stall_days = ? WHERE key = ? AND category = 'mine'", (days, key))
    conn.commit()
