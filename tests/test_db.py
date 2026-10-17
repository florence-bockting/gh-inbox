from ossinbox.storage import db


def test_move_old_data(tmp_path, monkeypatch):
    old, new = tmp_path / "gh-inbox", tmp_path / "oss-inbox"
    old.mkdir()
    (old / "state.db").write_text("x")
    monkeypatch.delenv("OSS_INBOX_DIR", raising=False)
    monkeypatch.delenv("GH_INBOX_DIR", raising=False)
    monkeypatch.setattr(db, "OLD_DATA_DIR", old)
    monkeypatch.setattr(db, "DATA_DIR", new)
    db.move_old_data()
    assert not old.exists()
    assert (new / "state.db").read_text() == "x"


def test_move_old_data_keeps_new_folder(tmp_path, monkeypatch):
    old, new = tmp_path / "gh-inbox", tmp_path / "oss-inbox"
    old.mkdir()
    new.mkdir()
    monkeypatch.delenv("OSS_INBOX_DIR", raising=False)
    monkeypatch.delenv("GH_INBOX_DIR", raising=False)
    monkeypatch.setattr(db, "OLD_DATA_DIR", old)
    monkeypatch.setattr(db, "DATA_DIR", new)
    db.move_old_data()
    assert old.exists()


def test_list_items_provider(tmp_path, monkeypatch):
    from ossinbox.core import items as core_items
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "state.db")
    conn = db.connect()
    db.set_setting(conn, "notes_file", str(tmp_path / "notes.csv"))
    for repo in ("owner/repo", "codeberg.org/owner/repo"):
        core_items.upsert(conn, {"key": repo + "#1", "category": "mine", "repo": repo,
                                 "number": 1, "kind": "issue",
                                 "updated_at": "2026-10-10T00:00:00Z"})
    got = {i["repo"]: i["provider"] for i in db.list_items(conn, "mine")}
    assert got == {"owner/repo": "GitHub", "codeberg.org/owner/repo": "Codeberg"}
