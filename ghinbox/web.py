"""Local web UI: a JSON API and one HTML page, served on 127.0.0.1 only."""

import threading
from wsgiref.simple_server import WSGIRequestHandler
from wsgiref.simple_server import make_server as wsgi_server

from flask import Flask, request
from werkzeug.exceptions import HTTPException

from . import db, osdeps, state, sync

HOST, PORT = "127.0.0.1", 8765
# Each POST must send this header. A browser cannot add it on a cross-site request
# without a preflight, and this server answers no preflight.
CSRF_HEADER = "X-GH-Inbox"
# The page loads only its own files. An injected inline script does not run.
CSP = "default-src 'self'; base-uri 'none'; frame-ancestors 'none'"


def create_app():
    app = Flask(__name__)
    # One connection for the page requests: db.connect() runs the schema each time.
    conn = db.connect()
    lock = threading.Lock()

    @app.before_request
    def check_request():
        if request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
            return {"error": "bad host"}, 403
        if request.method == "POST" and request.headers.get(CSRF_HEADER) != "1":
            return {"error": "forbidden"}, 403

    @app.after_request
    def add_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = CSP
        return response

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return {"error": exc.name.lower()}, exc.code

    @app.get("/")
    @app.get("/index.html")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/items")
    def items():
        args = request.args
        with lock:
            return db.list_items(conn, args.get("category", "action"),
                                 args.get("done") == "1", args.get("order") == "asc")

    @app.get("/api/repos")
    def repos():
        with lock:
            return db.list_repos(conn)

    @app.get("/api/status")
    def status():
        with lock:
            return state.status(conn)

    # Sync uses its own lock; do not block the other requests meanwhile.
    @app.post("/api/sync")
    def run_sync():
        return {"result": sync.sync(db.connect())}

    @app.post("/api/repos/load")
    def load_repos():
        try:
            sync.load_repo_candidates(db.connect())
        except Exception as exc:  # noqa: BLE001 - show every failure in the page
            return {"error": str(exc)}, 500
        return {"ok": True}

    @app.post("/api/<path:action>")
    def apply(action):
        if not request.get_data():
            body = {}
        else:
            body = request.get_json(force=True, silent=True)
            if body is None:
                return {"error": "bad json"}, 400
        with lock:
            try:
                state.apply(conn, action, body)
            except (KeyError, ValueError) as exc:
                return {"error": str(exc)}, 400
        return {"ok": True}

    return app


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def make_server():
    return wsgi_server(HOST, PORT, create_app(),
                       server_class=osdeps.ExclusiveWSGIServer, handler_class=QuietHandler)
