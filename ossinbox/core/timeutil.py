"""UTC times as ISO strings: the format of the forge APIs and of the database."""

from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso():
    return iso(utcnow())


def parse_iso(value):
    return datetime.fromisoformat(value) if value else None


def later(a, b):
    """True if ISO time a is after ISO time b (missing b counts as earlier)."""
    if not a:
        return False
    return not b or parse_iso(a) > parse_iso(b)
