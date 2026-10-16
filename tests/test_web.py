import pytest

from ghinbox import db, web


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "state.db")
    app = web.create_app()
    app.config["TESTING"] = True
    return app.test_client()


def post(client, path, body=None, **kwargs):
    return client.post(path, json=body, headers={web.CSRF_HEADER: "1"}, **kwargs)


def test_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.content_type == "text/html; charset=utf-8"
    assert r.headers["Cache-Control"] == "no-store"
    assert "<script>" not in r.text
    assert r.headers["Content-Security-Policy"] == web.CSP


@pytest.mark.parametrize("name", ["app.js", "app.css"])
def test_static_files(client, name):
    assert client.get(f"/static/{name}").status_code == 200


def test_bad_host(client):
    r = client.get("/api/status", base_url="http://evil.example")
    assert r.status_code == 403
    assert r.json == {"error": "bad host"}


def test_stop(client):
    calls = []
    client.application.config["STOP"] = lambda: calls.append(1)
    r = post(client, "/api/stop")
    assert r.json == {"ok": True}
    assert calls == []
    r.close()
    assert calls == [1]


def test_stop_without_server(client):
    assert post(client, "/api/stop").status_code == 400


def test_post_without_header(client):
    r = client.post("/api/items/all-done", json={"category": "action"})
    assert r.status_code == 403


def test_items_and_status(client):
    assert client.get("/api/items").json == []
    assert client.get("/api/repos").json == []
    assert "counts" in client.get("/api/status").json


def test_action(client):
    r = post(client, "/api/repos/add", {"full_name": "https://github.com/owner/repo"})
    assert r.json == {"ok": True}
    assert [repo["full_name"] for repo in client.get("/api/repos").json] == ["owner/repo"]


@pytest.mark.parametrize("path, body", [
    ("/api/no-such-action", {}),
    ("/api/repos/add", {}),
    ("/api/repos/add", {"full_name": "no-slash"}),
])
def test_bad_input(client, path, body):
    assert post(client, path, body).status_code == 400


def test_bad_json(client):
    r = client.post("/api/settings", data="{", headers={web.CSRF_HEADER: "1"})
    assert r.status_code == 400
    assert r.json == {"error": "bad json"}


def test_unknown_get(client):
    r = client.get("/api/nothing")
    assert r.status_code == 405
    assert r.json == {"error": "method not allowed"}


def test_bad_notes_path(client):
    r = post(client, "/api/settings", {"notes_file": "~no-such-user-xyz/notes.csv"})
    assert r.status_code == 400
