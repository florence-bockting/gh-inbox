"""Access tokens: one file for each forge in the data folder. Only you can read the files."""

import os

from . import db


def token_path(name):
    """The token file, for example "forgejo.token"."""
    return db.DATA_DIR / f"{name}.token"


def get_token(name):
    """The saved token, or "" when you did not save one."""
    try:
        return token_path(name).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def set_token(name, value):
    """Save the token in a file that only you can read. An empty value removes the file."""
    path = token_path(name)
    value = (value or "").strip()
    if not value:
        path.unlink(missing_ok=True)
        return
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(value)
    # An existing file keeps its old mode on O_CREAT.
    os.chmod(path, 0o600)
