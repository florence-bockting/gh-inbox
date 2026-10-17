"""The forges that the app syncs. To add a forge, add its provider to PROVIDERS."""

from .base import short_repo
from .forgejo import Forgejo
from .github import GitHub

# The sync order. GitHub first: its repo names have no host.
PROVIDERS = (GitHub(), Forgejo())


def provider_for(repo):
    """The forge of a stored repo name."""
    for provider in PROVIDERS:
        if provider.owns(repo):
            return provider
    raise KeyError(repo)


def repo_label(repo):
    """The repo name in the UIs: "GH owner/repo" or "CB owner/repo"."""
    return f"{provider_for(repo).prefix(repo)} {short_repo(repo)}"


def parse_repo(conn, text):
    """Turn "owner/repo" or a repo URL into the stored name. Raise ValueError if no forge
    knows it."""
    name = text.strip().removeprefix("https://").removeprefix("http://").strip("/")
    name = name.removesuffix(".git")
    for provider in PROVIDERS:
        found = provider.parse_repo(conn, name)
        if found:
            return found
    hosts = " or ".join(p.host(conn) for p in PROVIDERS)
    raise ValueError(f"use the form owner/repo, or a URL on {hosts}")
