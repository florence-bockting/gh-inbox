"""A Forgejo server, for example Codeberg. The repo names have the host as prefix."""

from ...storage import db, secrets
from ..base import repo_host
from . import client, sync


class Forgejo:
    name = "Codeberg"

    def enabled(self, conn):
        return bool(secrets.get_token(client.TOKEN_NAME))

    def owns(self, repo):
        return repo_host(repo) is not None

    def host(self, conn):
        return client.host(db.get_setting(conn, "forgejo_url"))

    def prefix(self, repo):
        """CB for Codeberg, FJ for another Forgejo server."""
        return "CB" if repo_host(repo) == "codeberg.org" else "FJ"

    def web_url(self, repo):
        return f"https://{repo}"

    def parse_repo(self, conn, name):
        parts = name.split("/")
        return name if len(parts) == 3 and parts[0] == self.host(conn) and all(parts) else None

    def sync(self, conn):
        return sync.sync(conn)

    def load_repo_candidates(self, conn):
        sync.load_repo_candidates(conn)

    def status(self, conn):
        token = self.enabled(conn)
        return {
            "forgejo_login": db.get_meta(conn, "forgejo_login") if token else None,
            # Only whether a token exists. The token itself never leaves the file.
            "forgejo_token": token,
        }
