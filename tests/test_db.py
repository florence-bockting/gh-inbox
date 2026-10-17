from ossinbox import db


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
