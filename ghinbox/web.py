"""Local web UI: a JSON API and one HTML page, served on 127.0.0.1 only."""

import json
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from . import db, osdeps, state, sync

HOST, PORT = "127.0.0.1", 8765
STATIC = Path(__file__).parent / "static"
# Each POST must send this header. A browser cannot add it on a cross-site request
# without a preflight, and this server answers no preflight.
CSRF_HEADER = "X-GH-Inbox"


class Handler(BaseHTTPRequestHandler):
    conn = None
    lock = threading.Lock()

    def log_message(self, *args):
        pass

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        path, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        if path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        with self.lock:
            if path == "/api/items":
                return self._send(200, db.list_items(
                    self.conn, params.get("category", "action"), params.get("done") == "1"))
            if path == "/api/repos":
                return self._send(200, db.list_repos(self.conn))
            if path == "/api/status":
                return self._send(200, state.status(self.conn))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok() or self.headers.get(CSRF_HEADER) != "1":
            return self._send(403, {"error": "forbidden"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})
        if self.path == "/api/sync":
            # Sync uses its own lock; do not block the other requests meanwhile.
            return self._send(200, {"result": sync.sync(db.connect())})
        if self.path == "/api/repos/load":
            try:
                sync.load_repo_candidates(db.connect())
            except Exception as exc:
                return self._send(500, {"error": str(exc)})
            return self._send(200, {"ok": True})
        with self.lock:
            try:
                state.apply(self.conn, self.path.removeprefix("/api/"), body)
            except (KeyError, ValueError) as exc:
                return self._send(400, {"error": str(exc)})
        self._send(200, {"ok": True})


def make_server():
    Handler.conn = db.connect()
    return osdeps.ExclusiveHTTPServer((HOST, PORT), Handler)
