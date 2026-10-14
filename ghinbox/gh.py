"""Thin wrapper around the `gh` CLI. Only GET requests: the app never writes to GitHub."""

import json
import subprocess


class GhError(RuntimeError):
    pass


def _decode_stream(text):
    """Decode one or more JSON values written one after another."""
    decoder = json.JSONDecoder()
    values, pos = [], 0
    text = text.strip()
    while pos < len(text):
        value, end = decoder.raw_decode(text, pos)
        values.append(value)
        pos = end
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return values


def api(path, paginate=False, jq=None):
    """Call `gh api` and return the decoded JSON values as a list."""
    cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json"]
    if paginate:
        cmd.append("--paginate")
    if jq:
        cmd += ["--jq", jq]
    cmd.append(path)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise GhError(f"gh api {path}: {proc.stderr.strip()}")
    return _decode_stream(proc.stdout)


def api_items(path, paginate=True, key=None):
    """Return the elements of a list endpoint (or of `.key` for search endpoints)."""
    jq = f".{key}[]" if key else ".[]"
    return api(path, paginate=paginate, jq=jq)


def api_one(path):
    values = api(path)
    return values[0] if values else None


# ---- conditional requests and rate limit ------------------------------------

# The core rate limit from the last response headers: remaining, limit, reset (epoch s).
RATE = {}


def request(path, etag=None):
    """GET one page with headers. Return (status, etag, body); body is None on 304.

    GitHub does not count a 304 answer against the rate limit.
    """
    cmd = ["gh", "api", "-i", "-H", "Accept: application/vnd.github+json"]
    if etag:
        cmd += ["-H", f"If-None-Match: {etag}"]
    cmd.append(path)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # gh exits with 1 on a 304, so read the status line, not the exit code.
    out = proc.stdout.replace("\r\n", "\n")
    head, _, body = out.partition("\n\n")
    lines = head.split("\n")
    if not lines[0].startswith("HTTP/"):
        raise GhError(f"gh api {path}: {proc.stderr.strip() or 'no response'}")
    status = int(lines[0].split()[1])
    headers = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    if headers.get("x-ratelimit-resource", "core") == "core" and "x-ratelimit-remaining" in headers:
        RATE.update(remaining=int(headers["x-ratelimit-remaining"]),
                    limit=int(headers["x-ratelimit-limit"]),
                    reset=int(headers["x-ratelimit-reset"]))
    if status >= 400:
        raise GhError(f"gh api {path}: HTTP {status} {body.strip()[:200]}")
    if status == 304:
        return status, etag, None
    return status, headers.get("etag"), json.loads(body) if body.strip() else None
