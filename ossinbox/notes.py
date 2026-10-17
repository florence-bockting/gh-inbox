"""Your notes on items, in a CSV file that you can also edit by hand.

The CSV is the only store of the notes. The setting `notes_file` gives its path.
"""

import csv
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from . import db, osdeps

FIELDS = ["key", "repo", "number", "title", "url", "note", "updated_at"]
LOCK_WAIT = 5  # seconds


def _path(value):
    try:
        path = Path(value).expanduser()
    except RuntimeError as exc:  # "~name" for a user that does not exist
        raise ValueError(f"{value}: {exc}") from exc
    # Windows does not fail for "~name". It guesses a folder next to your home folder.
    head = value.replace("\\", "/").split("/")[0]
    if head.startswith("~") and head != "~" and not Path(head).expanduser().is_dir():
        raise ValueError(f"{value}: no home folder for {head}")
    return path


def load(file):
    """Return {key: row}. A missing file means no notes."""
    try:
        with open(_path(file), newline="", encoding="utf-8") as f:
            return {r["key"]: r for r in csv.DictReader(f) if r.get("key")}
    except FileNotFoundError:
        return {}


@contextmanager
def _locked():
    """Hold the notes lock. The web page and the terminal UI can write at the same time."""
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + LOCK_WAIT
    while True:
        with osdeps.try_lock(db.DATA_DIR / "notes.lock") as locked:
            if locked:
                yield
                return
        if time.time() > deadline:
            raise ValueError("the notes file is busy, try again")
        time.sleep(0.1)


def save(file, item, body):
    """Add or change the note of one item. An empty body deletes the note."""
    target = _path(file)
    body = (body or "").strip()
    with _locked():
        rows = load(target)
        if body:
            rows[item["key"]] = {
                "key": item["key"], "repo": item["repo"], "number": item["number"] or "",
                "title": item["title"] or "", "url": item["url"] or "", "note": body,
                "updated_at": db.now_iso(),
            }
        elif rows.pop(item["key"], None) is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write a full new file, then replace the old one: a crash leaves no half file.
        tmp = target.with_name(target.name + ".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(sorted(rows.values(), key=lambda r: r["key"]))
        os.replace(tmp, target)


def move(old, new):
    """Move the notes file. Refuse when a file exists at the new path."""
    old, new = _path(old), _path(new)
    if old == new:
        return
    with _locked():
        if new.exists():
            raise ValueError(f"{new} exists already")
        if old.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(old, new)
