"""The contract that each forge fulfills, and the helpers for the repo names.

A repo name tells the forge. GitHub: "owner/repo". Another forge has the host as prefix:
"codeberg.org/owner/repo". So the same name on two forges stays two repos.
"""

from typing import Protocol


class ProviderError(RuntimeError):
    """A failed API request. Each forge client raises a subclass."""


def repo_host(repo):
    """The host of a repo on a forge other than GitHub, for example "codeberg.org"."""
    parts = repo.split("/")
    return parts[0] if len(parts) == 3 else None


def short_repo(repo):
    """The repo name without the host: "owner/repo"."""
    return repo.split("/", 1)[1] if repo_host(repo) else repo


class Provider(Protocol):
    """One forge. The sync, the UIs and the pop-ups use only these members."""

    # The forge name in error messages, for example "GitHub".
    name: str

    def enabled(self, conn) -> bool:
        """False when the forge needs a token that you did not save."""

    def owns(self, repo: str) -> bool:
        """True if the stored repo name belongs to this forge."""

    def host(self, conn) -> str:
        """The host name, for example "github.com"."""

    def prefix(self, repo: str) -> str:
        """The short forge label in the UIs, for example "GH"."""

    def web_url(self, repo: str) -> str:
        """The web page of the repo."""

    def parse_repo(self, conn, name: str) -> str | None:
        """The stored name for "owner/repo" or "host/owner/repo". None if it is not ours."""

    def sync(self, conn) -> str | None:
        """Sync the tabs. Return "ok" or "paused: ...". Raise on a failure."""

    def load_repo_candidates(self, conn) -> None:
        """Add the repos you watch or can push to, not watched yet."""

    def status(self, conn) -> dict:
        """The forge part of the status JSON, for example the login."""
