import sqlite3
import threading

from ossinbox import daemon
from ossinbox.storage import db


def test_failed_round_does_not_stop_poller(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "state.db")
    monkeypatch.setattr(daemon, "TICK_SECONDS", 0)
    stop = threading.Event()
    calls = []

    def poll_round(conn, last_sync):
        calls.append(1)
        if len(calls) == 1:
            raise sqlite3.OperationalError("database is locked")
        stop.set()
        return last_sync

    monkeypatch.setattr(daemon, "poll_round", poll_round)
    daemon.poll_loop(stop)
    assert len(calls) == 2
