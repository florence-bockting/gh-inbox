"""Fetch Codeberg (Forgejo) state and sort it into the tabs.

Forgejo notifications have no reason. So the issue search picks the tab:

action:   review requests, mentions and assignments in watched repos.
watch:    the other notifications in watched repos.
mine:     open issues and PRs you created, in any repo.

The repo names have the host as prefix, for example "codeberg.org/owner/repo".
"""

from datetime import timedelta

from ...core.items import auto_done, reopen_item, upsert
from ...core.timeutil import iso, utcnow
from ...storage import db, secrets
from . import client

# The searches for the Action tab, highest reason first: upsert keeps the higher reason.
ACTION_SEARCHES = (
    ("review_requested", {"review_requested": "true", "type": "pulls", "state": "open"}),
    # All states: a mention on a closed issue is done.
    ("mention", {"mentioned": "true", "state": "all"}),
    ("assign", {"assigned": "true", "state": "open"}),
)


class Api:
    """The Forgejo server from the settings, with the saved token."""

    def __init__(self, conn, token):
        self.base = db.get_setting(conn, "forgejo_url")
        self.host = client.host(self.base)
        self.token = token

    def one(self, path, **params):
        return client.get(self.base, self.token, path, params)

    def all(self, path, **params):
        return client.get_all(self.base, self.token, path, params)

    def repo(self, full_name):
        return f"{self.host}/{full_name}"


def _in_host(api):
    """SQL condition and parameter for the items of this server."""
    return "repo LIKE ?", f"{api.host}/%"


def _issue_item(api, it, category, reason):
    repo = api.repo(it["repository"]["full_name"])
    pull = it.get("pull_request")
    return {
        "key": f"{repo}#{it['number']}", "category": category, "repo": repo,
        "number": it["number"], "kind": "pr" if pull else "issue", "title": it["title"],
        "url": it["html_url"], "author": it["user"]["login"],
        "state": "draft" if pull and pull.get("draft") else it["state"],
        "reason": reason, "updated_at": it["updated_at"],
    }


def _thread_item(api, thread):
    repo = api.repo(thread["repository"]["full_name"])
    subject = thread["subject"]
    stype = subject.get("type")
    if stype in ("Issue", "Pull") and subject.get("url"):
        number = int(subject["url"].rstrip("/").rsplit("/", 1)[-1])
        kind, key = ("pr" if stype == "Pull" else "issue"), f"{repo}#{number}"
    else:
        number, kind, key = None, "other", f"{repo}:{stype}:{thread['id']}"
    return {
        "key": key, "repo": repo, "number": number, "kind": kind,
        "title": subject.get("title"), "state": subject.get("state"),
        "url": subject.get("html_url") or thread["repository"].get("html_url"),
        "reason": "subscribed", "event_at": thread["updated_at"], "unread": thread["unread"],
    }


def sync_notifications(conn, api, watched):
    """Put the notifications of watched repos in the Watch tab. Return the unread keys."""
    days = db.get_setting(conn, "new_item_days", float)
    since = db.get_meta(conn, "forgejo_notifications_since") \
        or iso(utcnow() - timedelta(days=days))
    started = utcnow()
    threads = {t["id"]: t for t in api.all("notifications", all="true", since=since)}
    for t in api.all("notifications"):
        threads[t["id"]] = t

    unread = set()
    for thread in threads.values():
        info = _thread_item(api, thread)
        if info.pop("unread"):
            unread.add(info["key"])
        db.add_repo(conn, info["repo"], source="notifications")
        if info["repo"] in watched:
            upsert(conn, dict(info, category="watch"))
    # Step back 10 minutes so that no update falls between two syncs.
    db.set_meta(conn, "forgejo_notifications_since", iso(started - timedelta(minutes=10)))
    return unread


def sync_action(conn, api, watched):
    """Search is the source of truth. An item that leaves all searches is done."""
    days = db.get_setting(conn, "new_item_days", float)
    since = iso(utcnow() - timedelta(days=days))
    found, assigned = set(), set()
    for reason, params in ACTION_SEARCHES:
        if reason == "mention":
            params = dict(params, since=since)
        for it in api.all("repos/issues/search", **params):
            item = _issue_item(api, it, "action", reason)
            if item["repo"] not in watched:
                continue
            row = conn.execute(
                "SELECT done, auto_done FROM items WHERE key = ? AND category = 'action'",
                (item["key"],)).fetchone()
            if it["state"] != "open":
                if row is not None:
                    auto_done(conn, item["key"], "action", it["state"])
                continue
            found.add(item["key"])
            if reason == "assign":
                assigned.add(item["key"])
            # No event_at on a known item: a higher reason stays.
            upsert(conn, dict(item, event_at=it["updated_at"] if row is None else None),
                   reopen=False)
            # Open it again after the app closed it, for example on a new review request.
            if row is not None and row["done"] and row["auto_done"]:
                reopen_item(conn, item["key"], "action")
    where, host = _in_host(api)
    for row in conn.execute(
            f"SELECT key, done, assigned, reason FROM items WHERE category = 'action' AND {where}",
            (host,)).fetchall():
        # The mention search sees recent updates only. An older mention stays until you
        # mark it done, or until the issue closes.
        if row["key"] not in found and not row["done"] and row["reason"] != "mention":
            auto_done(conn, row["key"], "action")
        now = int(row["key"] in assigned)
        if now != row["assigned"]:
            conn.execute("UPDATE items SET assigned = ? WHERE key = ? AND category = 'action'",
                         (now, row["key"]))


def sync_mine(conn, api, unread):
    found = set()
    for it in api.all("repos/issues/search", created="true", state="open"):
        item = _issue_item(api, it, "mine", "author")
        found.add(item["key"])
        upsert(conn, dict(item, event_at=it["created_at"]), reopen=False)
        conn.execute(
            "UPDATE items SET activity = ? WHERE key = ? AND category = 'mine'",
            (int(item["key"] in unread), item["key"]))
        # Reopened on Codeberg after the app closed it: show it again.
        conn.execute(
            "UPDATE items SET done = 0, done_at = NULL, auto_done = 0 "
            "WHERE key = ? AND category = 'mine' AND auto_done = 1", (item["key"],))
    where, host = _in_host(api)
    for row in conn.execute(
            f"SELECT key FROM items WHERE category = 'mine' AND done = 0 AND {where}",
            (host,)).fetchall():
        if row["key"] not in found:
            auto_done(conn, row["key"], "mine", "closed")


def sync(conn):
    """Run the Codeberg part of the sync. Return None when you saved no token."""
    token = secrets.get_token(client.TOKEN_NAME)
    if not token:
        return None
    api = Api(conn, token)
    db.set_meta(conn, "forgejo_login", api.one("user")["login"])
    watched = db.watched_repos(conn)
    unread = sync_notifications(conn, api, watched)
    sync_action(conn, api, watched)
    sync_mine(conn, api, unread)
    conn.commit()
    return "ok"


def load_repo_candidates(conn):
    """Add the Codeberg repos you watch and the repos you can push to (not watched yet)."""
    token = secrets.get_token(client.TOKEN_NAME)
    if not token:
        return
    api = Api(conn, token)
    for r in api.all("user/subscriptions"):
        db.add_repo(conn, api.repo(r["full_name"]), source="codeberg-watch")
    for r in api.all("user/repos"):
        db.add_repo(conn, api.repo(r["full_name"]), source="member")
    conn.commit()
