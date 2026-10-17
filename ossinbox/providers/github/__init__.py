"""GitHub, through the `gh` CLI. The repo names have no host: "owner/repo"."""

from ...storage import db
from ..base import repo_host
from . import ratelimit, sync


class GitHub:
    name = "GitHub"

    def enabled(self, conn):
        return True  # `gh` holds the login

    def owns(self, repo):
        return repo_host(repo) is None

    def host(self, conn):
        return "github.com"

    def prefix(self, repo):
        return "GH"

    def web_url(self, repo):
        return f"https://github.com/{repo}"

    def parse_repo(self, conn, name):
        parts = name.removeprefix("github.com/").split("/")
        return "/".join(parts) if len(parts) == 2 and all(parts) else None

    def sync(self, conn):
        return sync.sync(conn)

    def load_repo_candidates(self, conn):
        sync.load_repo_candidates(conn)

    def status(self, conn):
        return {
            "login": db.get_meta(conn, "login"),
            "rate": ratelimit.rate_status(conn),
            "estimate_per_hour": ratelimit.estimate_per_hour(conn),
            "last_sync_cost": db.get_meta(conn, "last_sync_cost"),
        }
