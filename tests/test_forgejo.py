import os
import sys

import pytest

from ossinbox import db, forgejo, state, sync, sync_forgejo

HOST = "codeberg.org"
REPO = "owner/repo"


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "state.db")
    return db.connect()


def issue(number, pull=False, state="open", repo=REPO):
    return {
        "number": number, "title": f"Item {number}", "state": state,
        "html_url": f"https://{HOST}/{repo}/{'pulls' if pull else 'issues'}/{number}",
        "user": {"login": "someone"}, "repository": {"full_name": repo},
        "pull_request": {"draft": False} if pull else None,
        "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-10T00:00:00Z",
    }


class FakeApi:
    """Answers the Forgejo paths that the sync uses."""

    def __init__(self):
        self.searches = {"review_requested": [], "mentioned": [], "assigned": [], "created": []}
        self.notifications = []

    def get(self, base, token, path, params=None):
        assert token == "secret"
        assert path == "user"
        return {"login": "me"}

    def get_all(self, base, token, path, params=None):
        params = params or {}
        if path == "notifications":
            return self.notifications
        if path == "repos/issues/search":
            (flag,) = [k for k in self.searches if params.get(k) == "true"]
            return self.searches[flag]
        raise AssertionError(path)


@pytest.fixture
def api(conn, monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr(forgejo, "get", fake.get)
    monkeypatch.setattr(forgejo, "get_all", fake.get_all)
    db.set_token("secret")
    db.add_repo(conn, f"{HOST}/{REPO}", watched=True)
    return fake


def items(conn, category):
    return {r["key"]: r for r in conn.execute(
        "SELECT * FROM items WHERE category = ?", (category,))}


def test_token_file(conn):
    assert db.get_token() == ""
    db.set_token(" secret \n")
    assert db.get_token() == "secret"
    if sys.platform != "win32":
        assert os.stat(db.token_path()).st_mode & 0o777 == 0o600
    st = state.status(conn)
    assert st["forgejo_token"] is True
    assert "secret" not in repr(st)
    db.set_token("")
    assert not db.token_path().exists()


@pytest.mark.parametrize("text, name", [
    ("owner/repo", "owner/repo"),
    ("https://github.com/owner/repo", "owner/repo"),
    ("https://codeberg.org/owner/repo", "codeberg.org/owner/repo"),
    ("https://codeberg.org/owner/repo.git", "codeberg.org/owner/repo"),
])
def test_repo_name(conn, text, name):
    assert state.repo_name(conn, text) == name


@pytest.mark.parametrize("text", ["repo", "https://example.org/owner/repo", "a/b/c/d"])
def test_repo_name_refuses(conn, text):
    with pytest.raises(ValueError):
        state.repo_name(conn, text)


def test_short_repo():
    assert db.short_repo(f"{HOST}/{REPO}") == REPO
    assert db.short_repo(REPO) == REPO
    assert db.repo_label(f"{HOST}/{REPO}") == f"CB {REPO}"
    assert db.repo_label("other.org/a/b") == "FJ a/b"
    assert db.repo_label(REPO) == f"GH {REPO}"


def test_no_token_skips(conn):
    assert sync_forgejo.sync(conn) is None


def test_sync_sorts_into_tabs(conn, api):
    api.searches["review_requested"] = [issue(1, pull=True)]
    api.searches["assigned"] = [issue(2)]
    api.searches["created"] = [issue(3, repo="me/other")]
    api.notifications = [{
        "id": 7, "unread": True, "updated_at": "2026-10-11T00:00:00Z",
        "repository": {"full_name": REPO, "html_url": f"https://{HOST}/{REPO}"},
        "subject": {"type": "Issue", "title": "Item 4", "state": "open",
                    "url": f"https://{HOST}/api/v1/repos/{REPO}/issues/4",
                    "html_url": f"https://{HOST}/{REPO}/issues/4"},
    }]
    assert sync_forgejo.sync(conn) == "ok"

    action = items(conn, "action")
    assert action[f"{HOST}/{REPO}#1"]["reason"] == "review_requested"
    assert action[f"{HOST}/{REPO}#1"]["kind"] == "pr"
    assert action[f"{HOST}/{REPO}#2"]["assigned"] == 1
    assert list(items(conn, "watch")) == [f"{HOST}/{REPO}#4"]
    assert list(items(conn, "mine")) == [f"{HOST}/me/other#3"]
    assert db.get_meta(conn, "forgejo_login") == "me"

    # You reviewed: the request left the search. The PR is done.
    api.searches["review_requested"] = []
    sync_forgejo.sync(conn)
    assert items(conn, "action")[f"{HOST}/{REPO}#1"]["done"] == 1


def test_closed_mention_is_done(conn, api):
    api.searches["mentioned"] = [issue(5)]
    sync_forgejo.sync(conn)
    assert items(conn, "action")[f"{HOST}/{REPO}#5"]["done"] == 0
    api.searches["mentioned"] = [issue(5, state="closed")]
    sync_forgejo.sync(conn)
    assert items(conn, "action")[f"{HOST}/{REPO}#5"]["done"] == 1


def test_unwatched_repo_is_skipped(conn, api):
    api.searches["assigned"] = [issue(6, repo="other/repo")]
    sync_forgejo.sync(conn)
    assert items(conn, "action") == {}


def test_github_items_stay(conn, api):
    """The Codeberg sync does not mark GitHub items done."""
    sync.upsert(conn, {"key": "owner/repo#9", "category": "mine", "repo": REPO,
                       "number": 9, "kind": "issue", "updated_at": "2026-10-10T00:00:00Z"})
    sync_forgejo.sync(conn)
    assert items(conn, "mine")["owner/repo#9"]["done"] == 0


def test_github_failure_does_not_stop_codeberg(conn, api, monkeypatch):
    def fail(conn):
        raise RuntimeError("gh is broken")

    monkeypatch.setattr(sync, "_sync_github", fail)
    api.searches["assigned"] = [issue(2)]
    result = sync.sync(conn)
    assert result == "error: GitHub: gh is broken"
    assert f"{HOST}/{REPO}#2" in items(conn, "action")
