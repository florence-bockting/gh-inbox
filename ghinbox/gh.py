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


def me():
    return api_one("user")["login"]
