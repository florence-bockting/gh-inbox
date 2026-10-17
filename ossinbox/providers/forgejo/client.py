"""Small client for the Forgejo API (Codeberg). Only GET requests: the app never writes."""

import json
import urllib.error
import urllib.parse
import urllib.request

from ..base import ProviderError

# Forgejo returns at most this many results on one page.
PAGE_LIMIT = 50
# The token file is "forgejo.token" in the data folder.
TOKEN_NAME = "forgejo"


class ForgejoError(ProviderError):
    pass


def host(base_url):
    """The host name, for example "codeberg.org". It is the prefix of the repo names."""
    return urllib.parse.urlsplit(base_url).netloc


def get(base_url, token, path, params=None):
    """GET one API path. Return the decoded JSON."""
    url = f"{base_url.rstrip('/')}/api/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace").strip()[:200]
        raise ForgejoError(f"GET {path}: HTTP {exc.code} {body}") from None
    except urllib.error.URLError as exc:
        raise ForgejoError(f"GET {path}: {exc.reason}") from None


def get_all(base_url, token, path, params=None):
    """GET every page of a list endpoint. Return one list."""
    out, page = [], 1
    while True:
        rows = get(base_url, token, path, dict(params or {}, page=page, limit=PAGE_LIMIT))
        out += rows
        if len(rows) < PAGE_LIMIT:
            return out
        page += 1
