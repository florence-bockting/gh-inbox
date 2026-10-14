"""Fetch GitHub state with `gh` and sort it into the three tabs.

action: review requests, @mentions and assignments in watched repos.
watch:  other notifications and new issues/PRs in watched repos.
mine:   open issues and PRs you authored, in any repo.
"""

import json
import time
from datetime import datetime, timedelta, timezone

from . import db, gh, osdeps

ACTION_PRIORITY = {"review_requested": 0, "mention": 1, "team_mention": 2, "assign": 3}


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _later(a, b):
    """True if ISO time a is after ISO time b (missing b counts as earlier)."""
    if not a:
        return False
    return not b or db.parse_iso(a) > db.parse_iso(b)


def _html_url(repo, kind, number):
    return f"https://github.com/{repo}/{'pull' if kind == 'pr' else 'issues'}/{number}"


# ---- upsert -----------------------------------------------------------------

def upsert(conn, item, reopen=True, bump=True):
    """Insert or update one item. Only GitHub fields change; your own settings stay.

    Return "new", "reopened", "newer" (newer event) or "updated".
    A done item opens again when a newer event arrives and `reopen` is true.
    With `bump` false, a newer event does not move `event_at`.
    """
    row = conn.execute(
        "SELECT * FROM items WHERE key = ? AND category = ?",
        (item["key"], item["category"])).fetchone()
    now = db.now_iso()
    if row is None:
        remind = None
        if item["category"] == "action":
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

    newer = _later(item.get("event_at"), row["event_at"])
    reason = row["reason"]
    if newer:
        reason = item.get("reason") or reason
    elif item["category"] == "action" and item.get("reason") in ACTION_PRIORITY:
        if ACTION_PRIORITY[item["reason"]] < ACTION_PRIORITY.get(reason, 99):
            reason = item["reason"]
    event_at = item["event_at"] if newer and bump else row["event_at"]
    conn.execute(
        "UPDATE items SET title = coalesce(?, title), url = coalesce(?, url), "
        "author = coalesce(?, author), state = coalesce(?, state), "
        "updated_at = coalesce(?, updated_at), reason = ?, event_at = ? "
        "WHERE key = ? AND category = ?",
        (item.get("title"), item.get("url"), item.get("author"), item.get("state"),
         item.get("updated_at"), reason, event_at, item["key"], item["category"]))
    if row["done"] and newer and reopen and _later(item["event_at"], row["done_at"]):
        _reopen(conn, item["key"], item["category"])
        return "reopened"
    return "newer" if newer else "updated"


def _reopen(conn, key, category):
    conn.execute(
        "UPDATE items SET done = 0, done_at = NULL, auto_done = 0, last_notified = NULL, "
        "notify_count = 0 WHERE key = ? AND category = ?", (key, category))


def _auto_done(conn, key, category, state=None):
    conn.execute(
        "UPDATE items SET done = 1, done_at = ?, auto_done = 1, state = coalesce(?, state) "
        "WHERE key = ? AND category = ? AND done = 0",
        (db.now_iso(), state, key, category))


# ---- notifications ----------------------------------------------------------

def _thread_item(thread):
    repo = thread["repository"]["full_name"]
    subject = thread["subject"]
    stype = subject.get("type")
    api_url = subject.get("url") or ""
    if stype in ("Issue", "PullRequest") and api_url:
        number = int(api_url.rstrip("/").rsplit("/", 1)[-1])
        kind = "pr" if stype == "PullRequest" else "issue"
        key, url = f"{repo}#{number}", _html_url(repo, kind, number)
    else:
        number, kind = None, "other"
        key = f"{repo}:{stype}:{thread['id']}"
        url = thread["repository"]["html_url"]
        if stype == "Discussion":
            url += "/discussions"
        elif stype == "Release":
            url += "/releases"
    return {
        "key": key, "repo": repo, "number": number, "kind": kind,
        "title": subject.get("title"), "url": url, "reason": thread["reason"],
        "event_at": thread["updated_at"], "unread": thread["unread"],
        "stype": stype,
    }


def sync_notifications(conn, watched):
    """Return the keys of items that have unread notifications."""
    days = db.get_setting(conn, "new_item_days", float)
    since = db.get_meta(conn, "notifications_since") or _iso(_utcnow() - timedelta(days=days))
    started = _utcnow()
    threads = {t["id"]: t for t in gh.api_items(f"notifications?all=true&since={since}")}
    for t in gh.api_items("notifications?all=false"):
        threads[t["id"]] = t

    unread, touched = set(), set()
    for thread in threads.values():
        info = _thread_item(thread)
        if info["unread"]:
            unread.add(info["key"])
        db.add_repo(conn, info["repo"], source="notifications")
        if info["repo"] not in watched:
            continue
        if info["reason"] in ACTION_PRIORITY:
            item = dict(info, category="action")
            # Review requests come from search (see sync_review_requests). Mentions
            # open again only when check_mentions finds a new mention.
            if info["reason"] == "review_requested":
                continue
            mention = info["reason"] in ("mention", "team_mention") and info["kind"] != "other"
            if upsert(conn, item, reopen=not mention, bump=not mention) != "updated":
                touched.add(info["key"])
        else:
            upsert(conn, dict(info, category="watch"))
    # Step back 10 minutes so that no update falls between two syncs.
    db.set_meta(conn, "notifications_since", _iso(started - timedelta(minutes=10)))
    return unread, touched


# ---- review requests --------------------------------------------------------

def sync_review_requests(conn, watched):
    """Search is the source of truth: GitHub removes you once you submit a review."""
    found = set()
    for pr in gh.api_items("search/issues?q=is:open+is:pr+review-requested:@me&per_page=100",
                           key="items"):
        repo = pr["repository_url"].split("/repos/", 1)[1]
        if repo not in watched:
            continue
        key = f"{repo}#{pr['number']}"
        found.add(key)
        row = conn.execute(
            "SELECT done, auto_done, reason FROM items WHERE key = ? AND category = 'action'",
            (key,)).fetchone()
        upsert(conn, {
            "key": key, "category": "action", "repo": repo, "number": pr["number"],
            "kind": "pr", "title": pr["title"], "url": pr["html_url"],
            "author": pr["user"]["login"], "state": pr["state"],
            "reason": "review_requested", "updated_at": pr["updated_at"],
        }, reopen=False)
        # Open it again after a re-request, or when a done mention became a review request.
        # A request you marked done yourself stays done while GitHub keeps it.
        if row is not None and row["done"] and (
                row["auto_done"] or row["reason"] != "review_requested"):
            _reopen(conn, key, "action")
    # A request that left the search result: you reviewed, or it was withdrawn.
    for row in conn.execute(
            "SELECT key FROM items WHERE category = 'action' AND done = 0 "
            "AND reason = 'review_requested'").fetchall():
        if row["key"] not in found:
            _auto_done(conn, row["key"], "action")
    return found


def sync_mentions(conn, watched, touched):
    """Find mentions with search too: GitHub does not always send a notification.

    Add the key of each new or changed item to `touched`.
    """
    days = db.get_setting(conn, "new_item_days", float)
    since = _iso(_utcnow() - timedelta(days=days))
    for it in gh.api_items(f"search/issues?q=is:open+mentions:@me+updated:>={since}"
                           "&per_page=100", key="items"):
        repo = it["repository_url"].split("/repos/", 1)[1]
        if repo not in watched:
            continue
        key = f"{repo}#{it['number']}"
        row = conn.execute(
            "SELECT updated_at FROM items WHERE key = ? AND category = 'action'",
            (key,)).fetchone()
        # No event_at on a known item: a higher reason (a review request) stays.
        upsert(conn, {
            "key": key, "category": "action", "repo": repo, "number": it["number"],
            "kind": "pr" if "pull_request" in it else "issue", "title": it["title"],
            "url": it["html_url"], "author": it["user"]["login"], "state": it["state"],
            "reason": "mention", "updated_at": it["updated_at"],
            "event_at": it["updated_at"] if row is None else None,
        }, reopen=False)
        if row is None or row["updated_at"] != it["updated_at"]:
            touched.add(key)


# ---- mentions and assignments -----------------------------------------------

def _comments(repo, number, kind):
    """Return (created_at, login, body) for every comment, review and review comment."""
    out = []
    for c in gh.api_items(f"repos/{repo}/issues/{number}/comments?per_page=100"):
        out.append((c["created_at"], c["user"]["login"], c.get("body") or ""))
    if kind == "pr":
        for c in gh.api_items(f"repos/{repo}/pulls/{number}/comments?per_page=100"):
            out.append((c["created_at"], c["user"]["login"], c.get("body") or ""))
        for r in gh.api_items(f"repos/{repo}/pulls/{number}/reviews?per_page=100"):
            if r.get("submitted_at"):
                out.append((r["submitted_at"], r["user"]["login"], r.get("body") or ""))
    return out


def check_action_items(conn, login, touched):
    """Mark mentions and assignments done when you acted. Open them again on a new mention.

    Open items cost one request per sync. Comments load only when the issue changed.
    """
    rows = conn.execute(
        "SELECT * FROM items WHERE category = 'action' AND kind IN ('issue', 'pr') "
        "AND reason IN ('mention', 'team_mention', 'assign')").fetchall()
    tag = f"@{login.lower()}"
    for row in rows:
        if row["done"] and row["key"] not in touched:
            continue
        _, issue = db.cached_get(conn, f"repos/{row['repo']}/issues/{row['number']}",
                                 keep_body=True)
        conn.execute(
            "UPDATE items SET title = ?, author = ?, state = ?, updated_at = ? "
            "WHERE key = ? AND category = 'action'",
            (issue["title"], issue["user"]["login"], issue["state"], issue["updated_at"],
             row["key"]))
        if issue["state"] == "closed":
            _auto_done(conn, row["key"], "action", "closed")
            continue
        if row["reason"] == "assign":
            assignees = {a["login"] for a in issue.get("assignees") or []}
            if login not in assignees:
                _auto_done(conn, row["key"], "action")
            continue
        if row["updated_at"] == issue["updated_at"] and row["key"] not in touched:
            continue

        comments = _comments(row["repo"], row["number"], row["kind"])
        my_reply = max((t for t, who, _ in comments if who == login), default=None)
        if row["reason"] == "mention":
            mentions = [t for t, who, body in comments if who != login and tag in body.lower()]
            if tag in (issue.get("body") or "").lower():
                mentions.append(issue["created_at"])
            mention_at = max(mentions, default=row["event_at"])
        else:
            mention_at = row["event_at"]

        if _later(my_reply, mention_at):
            _auto_done(conn, row["key"], "action")
        elif row["done"]:
            if _later(mention_at, row["done_at"]):
                _reopen(conn, row["key"], "action")
                conn.execute(
                    "UPDATE items SET event_at = ? WHERE key = ? AND category = 'action'",
                    (mention_at, row["key"]))
        elif _later(mention_at, row["event_at"]):
            # A new mention on an open item: notify again now.
            conn.execute(
                "UPDATE items SET event_at = ?, last_notified = NULL "
                "WHERE key = ? AND category = 'action'", (mention_at, row["key"]))


# ---- new issues and PRs in watched repos ------------------------------------

def sync_new_items(conn, login):
    days = db.get_setting(conn, "new_item_days", float)
    for repo in db.list_repos(conn):
        if not repo["watched"]:
            continue
        cutoff = db.parse_iso(repo["watch_since"]) - timedelta(days=days)
        # A shorter watch history removes the new items that are now too old.
        conn.execute(
            "DELETE FROM items WHERE repo = ? AND category = 'watch' "
            "AND reason IN ('new_issue', 'new_pr') AND event_at < ?",
            (repo["full_name"], _iso(cutoff)))
        changed, issues = db.cached_get(
            conn, f"repos/{repo['full_name']}/issues?state=all&sort=created&direction=desc"
            "&per_page=50", context=f"{repo['watch_since']}|{days}")
        if not changed:
            continue
        for it in issues:
            if db.parse_iso(it["created_at"]) < cutoff:
                break
            if it["user"]["login"] == login:
                continue
            kind = "pr" if "pull_request" in it else "issue"
            upsert(conn, {
                "key": f"{repo['full_name']}#{it['number']}", "category": "watch",
                "repo": repo["full_name"], "number": it["number"], "kind": kind,
                "title": it["title"], "url": it["html_url"], "author": it["user"]["login"],
                "state": it["state"], "reason": f"new_{kind}", "event_at": it["created_at"],
                "updated_at": it["updated_at"],
            }, reopen=False)


# ---- my open work -----------------------------------------------------------

def sync_mine(conn, unread):
    found = set()
    for it in gh.api_items("search/issues?q=is:open+author:@me+archived:false&per_page=100",
                           key="items"):
        repo = it["repository_url"].split("/repos/", 1)[1]
        kind = "pr" if "pull_request" in it else "issue"
        key = f"{repo}#{it['number']}"
        found.add(key)
        upsert(conn, {
            "key": key, "category": "mine", "repo": repo, "number": it["number"],
            "kind": kind, "title": it["title"], "url": it["html_url"],
            "author": it["user"]["login"], "state": "draft" if it.get("draft") else it["state"],
            "reason": "author", "event_at": it["created_at"], "updated_at": it["updated_at"],
        }, reopen=False)
        conn.execute(
            "UPDATE items SET activity = ? WHERE key = ? AND category = 'mine'",
            (int(key in unread), key))
        # Reopened on GitHub after the app closed it: show it again.
        conn.execute(
            "UPDATE items SET done = 0, done_at = NULL, auto_done = 0 "
            "WHERE key = ? AND category = 'mine' AND auto_done = 1", (key,))
    for row in conn.execute(
            "SELECT key FROM items WHERE category = 'mine' AND done = 0").fetchall():
        if row["key"] not in found:
            _auto_done(conn, row["key"], "mine", "closed")


def refresh_stalled(conn):
    """Flag your items with no activity for longer than their stall time."""
    default_days = db.get_setting(conn, "stall_days", float)
    now = _utcnow()
    for row in conn.execute(
            "SELECT key, updated_at, stall_days, stalled FROM items "
            "WHERE category = 'mine' AND done = 0").fetchall():
        days = row["stall_days"] if row["stall_days"] is not None else default_days
        idle = now - db.parse_iso(row["updated_at"])
        stalled = int(days > 0 and idle >= timedelta(days=days))
        if stalled != row["stalled"]:
            conn.execute(
                "UPDATE items SET stalled = ?, last_notified = NULL, notify_count = 0 "
                "WHERE key = ? AND category = 'mine'", (stalled, row["key"]))
    conn.commit()


# ---- repo candidates --------------------------------------------------------

def load_repo_candidates(conn):
    """Add the repos you watch on GitHub and the repos you can push to (not watched yet)."""
    for r in gh.api_items("user/subscriptions?per_page=100"):
        db.add_repo(conn, r["full_name"], source="github-watch")
    for r in gh.api_items(
            "user/repos?affiliation=owner,collaborator,organization_member&per_page=100"):
        db.add_repo(conn, r["full_name"], source="member")
    conn.commit()


# ---- rate limit -------------------------------------------------------------

# Below this share of the hourly limit, the sync waits for the reset.
PAUSE_SHARE = 0.10
# Below this share, the UIs show a warning and the daemon sends one pop-up.
WARN_SHARE = 0.20


def _store_rate(conn):
    rate = dict(gh.RATE)
    if rate:
        db.set_meta(conn, "rate", json.dumps(rate))
    return rate or None


def _clock(epoch):
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
    rate["reset_clock"] = _clock(rate["reset"])
    return rate


def estimate_per_hour(conn):
    """Most requests each hour, if no ETag answer is 304."""
    minutes = db.get_setting(conn, "poll_minutes", float)
    open_checks = conn.execute(
        "SELECT count(*) FROM items WHERE category = 'action' AND done = 0 "
        "AND reason IN ('mention', 'team_mention', 'assign')").fetchone()[0]
    per_sync = 6 + len(db.watched_repos(conn)) + open_checks
    return round(per_sync * 60 / max(minutes, 1))


# ---- entry point ------------------------------------------------------------

def sync(conn):
    """Run one full sync. Return a status string. Only one sync runs at a time."""
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with osdeps.try_lock(db.DATA_DIR / "sync.lock") as locked:
        if not locked:
            return "busy"
        try:
            # A 304 on `user` is free and still reports the rate limit.
            _, user = db.cached_get(conn, "user", keep_body=True)
            login = user["login"]
            db.set_meta(conn, "login", login)
            start = _store_rate(conn)
            if start and start["remaining"] < PAUSE_SHARE * start["limit"] \
                    and time.time() < start["reset"]:
                db.set_meta(conn, "paused_until", str(start["reset"]))
                return "paused: few API requests left until " + _clock(start["reset"])
            db.set_meta(conn, "paused_until", "")
            watched = db.watched_repos(conn)
            unread, touched = sync_notifications(conn, watched)
            sync_review_requests(conn, watched)
            sync_mentions(conn, watched, touched)
            check_action_items(conn, login, touched)
            sync_new_items(conn, login)
            sync_mine(conn, unread)
            conn.commit()
            refresh_stalled(conn)
            db.cached_get(conn, "user", keep_body=True)
            end = _store_rate(conn)
            if start and end and start["reset"] == end["reset"]:
                db.set_meta(conn, "last_sync_cost", str(start["remaining"] - end["remaining"]))
            db.set_meta(conn, "last_sync", db.now_iso())
            db.set_meta(conn, "last_error", "")
            return "ok"
        except Exception as exc:  # report every failure in the UI
            conn.rollback()
            db.set_meta(conn, "last_error", f"{db.now_iso()} {exc}")
            return f"error: {exc}"
