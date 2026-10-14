"""Fetch GitHub state with `gh` and sort it into the four tabs.

action:   review requests, @mentions and assignments in watched repos.
watch:    other notifications and new issues/PRs in watched repos.
mine:     open issues and PRs you authored, in any repo.
todo:     issues and PRs where you mentioned yourself, in watched repos.
"""

import json
import re
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
    """Find mentions and assignments with search too: GitHub does not always send a
    notification. Mentions are recent ones only. Assignments are all open ones.

    Add the key of each new or changed item to `touched`.
    """
    days = db.get_setting(conn, "new_item_days", float)
    since = _iso(_utcnow() - timedelta(days=days))
    _sync_search(conn, watched, touched, f"mentions:@me+updated:>={since}", "mention")
    assigned = _sync_search(conn, watched, touched, "assignee:@me", "assign")
    for row in conn.execute(
            "SELECT key, done, assigned FROM items WHERE category = 'action'").fetchall():
        now = row["key"] in assigned
        if now == bool(row["assigned"]):
            continue
        # A new assignment opens a done item again.
        if now and row["done"]:
            _reopen(conn, row["key"], "action")
        conn.execute("UPDATE items SET assigned = ? WHERE key = ? AND category = 'action'",
                     (int(now), row["key"]))


def _sync_search(conn, watched, touched, query, reason):
    """Return the keys that the search found."""
    found = set()
    for it in gh.api_items(f"search/issues?q=is:open+{query}&per_page=100", key="items"):
        repo = it["repository_url"].split("/repos/", 1)[1]
        if repo not in watched:
            continue
        key = f"{repo}#{it['number']}"
        found.add(key)
        row = conn.execute(
            "SELECT updated_at FROM items WHERE key = ? AND category = 'action'",
            (key,)).fetchone()
        # No event_at on a known item: a higher reason (a review request) stays.
        upsert(conn, {
            "key": key, "category": "action", "repo": repo, "number": it["number"],
            "kind": "pr" if "pull_request" in it else "issue", "title": it["title"],
            "url": it["html_url"], "author": it["user"]["login"], "state": it["state"],
            "reason": reason, "updated_at": it["updated_at"],
            "event_at": it["updated_at"] if row is None else None,
        }, reopen=False)
        if row is None or row["updated_at"] != it["updated_at"]:
            touched.add(key)
    return found


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
        # Your own @login in your comment is a to-do, not a reply.
        my_reply = max((t for t, who, body in comments
                        if who == login and tag not in body.lower()), default=None)
        if row["reason"] == "mention":
            mentions = [t for t, who, body in comments if who != login and tag in body.lower()]
            todos = [t for t, who, body in comments if who == login and tag in body.lower()]
            if tag in (issue.get("body") or "").lower():
                own = issue["user"]["login"] == login
                (todos if own else mentions).append(issue["created_at"])
            if todos:
                _add_todo(conn, row, issue, max(todos))
                # Only you mentioned yourself: the item shows in the ToDo tab only.
                if not mentions and not row["assigned"]:
                    _auto_done(conn, row["key"], "action")
                    continue
            mention_at = max(mentions, default=row["event_at"])
        else:
            mention_at = row["event_at"]

        # A mention stays open while you are an assignee.
        if _later(my_reply, mention_at) and not row["assigned"]:
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


def _add_todo(conn, row, issue, at):
    """Add or update the to-do for a self-mention. A newer self-mention opens it again."""
    upsert(conn, {
        "key": row["key"], "category": "todo", "repo": row["repo"],
        "number": row["number"], "kind": row["kind"], "title": issue["title"],
        "url": row["url"], "author": issue["user"]["login"], "state": issue["state"],
        "reason": "todo", "updated_at": issue["updated_at"], "event_at": at,
    })


def check_todos(conn):
    """Mark a to-do done when its issue or PR closes. One request for each open to-do."""
    for row in conn.execute(
            "SELECT key, repo, number FROM items WHERE category = 'todo' AND done = 0"
            ).fetchall():
        _, issue = db.cached_get(conn, f"repos/{row['repo']}/issues/{row['number']}",
                                 keep_body=True)
        conn.execute(
            "UPDATE items SET title = ?, state = ?, updated_at = ? "
            "WHERE key = ? AND category = 'todo'",
            (issue["title"], issue["state"], issue["updated_at"], row["key"]))
        if issue["state"] == "closed":
            _auto_done(conn, row["key"], "todo", "closed")


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


# ---- reviews you wait for ---------------------------------------------------

def _tags(name, body):
    """True if `body` tags @name. "@ab" does not tag "@abc" or "@ab-c"."""
    return re.search(rf"(?<![\w-])@{re.escape(name)}(?![\w-])", body, re.IGNORECASE) is not None


def _review_starts(repo, number, pending, login):
    """Return {reviewer: start}. The timer of a reviewer starts at the last review
    request, or at your last comment that tags the reviewer."""
    owner = repo.split("/")[0]
    starts = {}
    for ev in gh.api_items(f"repos/{repo}/issues/{number}/timeline?per_page=100"):
        if ev.get("event") == "review_requested":
            user = (ev.get("requested_reviewer") or {}).get("login")
            team = (ev.get("requested_team") or {}).get("slug")
            name = user or (f"{owner}/{team}" if team else None)
            if name in pending:
                starts[name] = ev["created_at"]
        elif ev.get("event") == "commented" and (ev.get("actor") or {}).get("login") == login:
            for name in pending:
                if _tags(name, ev.get("body") or ""):
                    starts[name] = ev["created_at"]
    return starts


def refresh_waiting(conn, login):
    """Flag your PRs where a requested review waits longer than review_wait_days.

    One request for each open PR. The timeline loads only when the PR changed.
    """
    days = db.get_setting(conn, "review_wait_days", float)
    now = _utcnow()
    for row in conn.execute(
            "SELECT key, repo, number, updated_at, review_waits, review_checked, waiting_for "
            "FROM items WHERE category = 'mine' AND kind = 'pr' AND done = 0").fetchall():
        waits = {}
        if days > 0:
            changed, req = db.cached_get(
                conn, f"repos/{row['repo']}/pulls/{row['number']}/requested_reviewers",
                keep_body=True)
            owner = row["repo"].split("/")[0]
            pending = [u["login"] for u in req.get("users") or []] + \
                [f"{owner}/{t['slug']}" for t in req.get("teams") or []]
            waits = {n: t for n, t in json.loads(row["review_waits"] or "{}").items()
                     if n in pending}
            if pending and (changed or set(pending) != set(waits)
                            or row["review_checked"] != row["updated_at"]):
                starts = _review_starts(row["repo"], row["number"], pending, login)
                # No request event found: the timer starts now.
                waits = {n: starts.get(n) or waits.get(n) or _iso(now) for n in pending}
        overdue = sorted(n for n, t in waits.items()
                         if now - db.parse_iso(t) >= timedelta(days=days))
        waiting_for = ", ".join(overdue) or None
        conn.execute(
            "UPDATE items SET review_waits = ?, review_checked = ?, waiting_for = ?, "
            "waiting_since = ? WHERE key = ? AND category = 'mine'",
            (json.dumps(waits) if waits else None, row["updated_at"], waiting_for,
             min((waits[n] for n in overdue), default=None), row["key"]))
        # A new overdue reviewer gives a new pop-up.
        if waiting_for != row["waiting_for"]:
            conn.execute(
                "UPDATE items SET last_notified = NULL, notify_count = 0 "
                "WHERE key = ? AND category = 'mine'", (row["key"],))


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
        "SELECT count(*) FROM items WHERE done = 0 AND (category = 'todo' OR "
        "(category = 'action' AND reason IN ('mention', 'team_mention', 'assign')))"
        ).fetchone()[0]
    open_prs = conn.execute(
        "SELECT count(*) FROM items WHERE category = 'mine' AND kind = 'pr' AND done = 0"
        ).fetchone()[0]
    per_sync = 6 + len(db.watched_repos(conn)) + open_checks + open_prs
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
            check_todos(conn)
            sync_new_items(conn, login)
            sync_mine(conn, unread)
            refresh_waiting(conn, login)
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
