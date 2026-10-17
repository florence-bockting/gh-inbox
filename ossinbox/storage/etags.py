"""The stored ETags of GET requests, for conditional requests. No HTTP here."""

import json


def load(conn, path, context=""):
    """Return (etag, body) for `path`. Both are None when nothing is stored.

    The ETag is None when the stored `context` differs. The body is the stored body,
    or None when the caller did not keep it.
    """
    row = conn.execute("SELECT * FROM etags WHERE path = ?", (path,)).fetchone()
    if row is None:
        return None, None
    etag = row["etag"] if row["context"] == context else None
    return etag, json.loads(row["body"]) if row["body"] else None


def store(conn, path, context, etag, body=None):
    """Store the ETag in the open transaction. A rollback removes it again."""
    conn.execute(
        "INSERT OR REPLACE INTO etags (path, context, etag, body) VALUES (?, ?, ?, ?)",
        (path, context, etag, None if body is None else json.dumps(body)))
