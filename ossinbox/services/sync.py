"""Run one sync of every forge in the registry. Only one sync runs at a time."""

from .. import osdeps
from ..core import items
from ..core.timeutil import now_iso
from ..providers import registry
from ..storage import db


def sync(conn):
    """Run one full sync. Return a status string.

    The forges sync one after the other. A failure of one does not stop the others.
    """
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with osdeps.try_lock(db.DATA_DIR / "sync.lock") as locked:
        if not locked:
            return "busy"
        results, errors = [], []
        for provider in registry.PROVIDERS:
            if not provider.enabled(conn):
                continue
            try:
                result = provider.sync(conn)
            except Exception as exc:  # noqa: BLE001 - report every failure in the UI
                conn.rollback()
                errors.append(f"{provider.name}: {exc}")
                continue
            if result and result != "ok":
                results.append(result)
        items.refresh_stalled(conn)
        if errors:
            db.set_meta(conn, "last_error", f"{now_iso()} {'; '.join(errors)}")
            return "error: " + "; ".join(errors)
        if results:
            return results[0]  # paused
        db.set_meta(conn, "last_sync", now_iso())
        db.set_meta(conn, "last_error", "")
        return "ok"


def load_repo_candidates(conn):
    """Add the repos you watch and the repos you can push to, on each enabled forge."""
    for provider in registry.PROVIDERS:
        if provider.enabled(conn):
            provider.load_repo_candidates(conn)
