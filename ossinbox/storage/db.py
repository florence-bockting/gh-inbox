"""SQLite state: watched repos, items per tab, settings."""

import os
import sqlite3
from pathlib import Path

from ..core.timeutil import now_iso

# The app had the name gh-inbox before. The old environment variable still works.
DATA_DIR = Path(os.environ.get("OSS_INBOX_DIR") or os.environ.get("GH_INBOX_DIR")
                or Path.home() / ".local/share/oss-inbox")
OLD_DATA_DIR = Path.home() / ".local/share/gh-inbox"
DB_PATH = DATA_DIR / "state.db"

DEFAULT_SETTINGS = {
    "poll_minutes": "60",
    "default_remind_hours": "24",
    "stall_days": "30",
    "review_wait_days": "3",
    "notify": "1",
    "new_item_days": "14",
    "notes_file": "~/oss-inbox/notes.csv",
    "forgejo_url": "https://codeberg.org",
}
# The other settings are numeric.
TEXT_SETTINGS = {"notes_file", "forgejo_url"}

TABS = ("action", "watch", "mine", "todo")
# The tab that shows an item: the tab you moved it to, or the tab that the sync chose.
SHOWN = "coalesce(moved_to, category)"

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
    assigned      INTEGER NOT NULL DEFAULT 0,   -- you are an assignee (Action only)
    moved_to      TEXT,               -- the tab you moved the item to
    priority      INTEGER NOT NULL DEFAULT 0,   -- 1 = pinned: first in the list
    review_waits  TEXT,               -- JSON {reviewer: start} of your PR (My work only)
    review_checked TEXT,              -- updated_at when the app last read the timeline
    waiting_for   TEXT,               -- overdue reviewers, for example "x, org/team"
    waiting_since TEXT,               -- the oldest start of the overdue reviewers
    PRIMARY KEY (key, category)
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS etags (
    path    TEXT PRIMARY KEY,
    context TEXT,                     -- the ETag is valid only for this context
    etag    TEXT,
    body    TEXT                      -- JSON, kept only when the caller needs it on 304
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def move_old_data():
    """Move the data folder of gh-inbox to the new name. Only the first start does this."""
    if os.environ.get("OSS_INBOX_DIR") or os.environ.get("GH_INBOX_DIR"):
        return
    if OLD_DATA_DIR.is_dir() and not DATA_DIR.exists():
        OLD_DATA_DIR.rename(DATA_DIR)


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    # A database from an older version does not have all the columns.
    have = {r["name"] for r in conn.execute("PRAGMA table_info(items)")}
    for column, decl in [("assigned", "INTEGER NOT NULL DEFAULT 0"), ("moved_to", "TEXT"),
                         ("priority", "INTEGER NOT NULL DEFAULT 0"), ("review_waits", "TEXT"),
                         ("review_checked", "TEXT"), ("waiting_for", "TEXT"),
                         ("waiting_since", "TEXT")]:
        if column not in have:
            conn.execute(f"ALTER TABLE items ADD COLUMN {column} {decl}")
    # The ToDo tab had the name "reminder" before.
    conn.execute("UPDATE items SET category = 'todo', reason = 'todo' WHERE category = 'reminder'")
    conn.execute("UPDATE items SET moved_to = 'todo' WHERE moved_to = 'reminder'")
    # Overdue PRs from before the pin get a pin one time. Your later unpins stay.
    if not get_meta(conn, "pinned_overdue"):
        conn.execute("UPDATE items SET priority = 1 WHERE waiting_for IS NOT NULL")
        set_meta(conn, "pinned_overdue", "1")
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
    if key in TEXT_SETTINGS:
        value = str(value).strip()
        if not value:
            raise ValueError(f"{key} must not be empty")
    else:
        float(value)
    if key == "notes_file":
        from . import notes  # notes imports db
        notes.move(get_setting(conn, key), value)
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
            "DELETE FROM items WHERE repo = ? AND category IN ('action', 'watch', 'todo')", (full_name,))
    conn.commit()


# ---- items ------------------------------------------------------------------

def list_items(conn, category, show_done=False, oldest_first=False):
    """Newest first: by the last event, or by the last update in My work."""
    sql = f"SELECT *, {SHOWN} AS tab FROM items WHERE {SHOWN} = ?"
    if not show_done:
        sql += " AND done = 0"
    # A moved item hides when the target tab has the same issue of its own.
    sql += (" AND NOT (moved_to IS NOT NULL AND EXISTS (SELECT 1 FROM items b"
            " WHERE b.key = items.key AND b.category = items.moved_to AND b.moved_to IS NULL))")
    if category == "watch":
        # An item that needs your action shows only in the Action tab.
        sql += (" AND NOT EXISTS (SELECT 1 FROM items a WHERE a.key = items.key"
                " AND coalesce(a.moved_to, a.category) = 'action' AND a.done = 0)")
    when = "updated_at" if category == "mine" else "coalesce(event_at, updated_at)"
    # Pinned items first, in both orders.
    sql += (f" ORDER BY priority DESC, "
            f"{when} {'ASC' if oldest_first else 'DESC'}")
    from ..providers import registry  # the providers import db
    from . import notes  # notes imports db
    saved = notes.load(get_setting(conn, "notes_file"))
    items = [dict(r) for r in conn.execute(sql, (category,))]
    for it in items:
        it["note"] = (saved.get(it["key"]) or {}).get("note") or ""
        it["provider"] = registry.provider_for(it["repo"]).name
    return items


def counts(conn):
    rows = conn.execute(
        f"SELECT {SHOWN} AS tab, count(*) AS n FROM items WHERE done = 0 GROUP BY tab")
    return {r["tab"]: r["n"] for r in rows}


def set_done(conn, key, category, done):
    conn.execute(
        "UPDATE items SET done = ?, done_at = ?, auto_done = 0 WHERE key = ? AND category = ?",
        (int(done), now_iso() if done else None, key, category))
    conn.commit()


def mark_all_done(conn, category):
    conn.execute(
        f"UPDATE items SET done = 1, done_at = ?, auto_done = 0 WHERE {SHOWN} = ? AND done = 0",
        (now_iso(), category))
    conn.commit()


def set_priority(conn, key, category, high):
    conn.execute("UPDATE items SET priority = ? WHERE key = ? AND category = ?",
                 (int(high), key, category))
    conn.commit()


def move_item(conn, key, category, target):
    """Show the item in the tab `target`. The sync still updates it in `category`."""
    if target not in TABS:
        raise ValueError(f"unknown tab {target}")
    row = conn.execute(f"SELECT {SHOWN} AS tab FROM items WHERE key = ? AND category = ?",
                       (key, category)).fetchone()
    if row is None:
        raise KeyError(key)
    conn.execute("UPDATE items SET moved_to = ? WHERE key = ? AND category = ?",
                 (None if target == category else target, key, category))
    if target in ("action", "todo") and row["tab"] != target:
        # The first pop-up comes after the reminder interval, not now.
        conn.execute(
            "UPDATE items SET last_notified = ?, notify_count = 1 WHERE key = ? AND category = ?",
            (now_iso(), key, category))
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
