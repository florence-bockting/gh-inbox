"""Command line: gh-inbox daemon | web | tui | sync | test-popup."""

import argparse
import urllib.request
import webbrowser

from . import db, osdeps, sync, web


def _daemon_up():
    try:
        urllib.request.urlopen(f"http://{web.HOST}:{web.PORT}/api/status", timeout=2)
        return True
    except OSError:
        return False


def cmd_web():
    url = f"http://{web.HOST}:{web.PORT}"
    if _daemon_up():
        webbrowser.open(url)
        return
    from . import daemon
    webbrowser.open(url)
    daemon.main()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gh-inbox", description="A better GitHub notifications inbox.")
    parser.add_argument("command", choices=["daemon", "web", "tui", "sync", "test-popup"])
    args = parser.parse_args(argv)
    if args.command == "daemon":
        from . import daemon
        daemon.main()
    elif args.command == "web":
        cmd_web()
    elif args.command == "tui":
        from . import tui
        tui.main()
    elif args.command == "sync":
        print(sync.sync(db.connect()))
    elif args.command == "test-popup":
        osdeps.notify("GitHub Inbox test", "A normal pop-up.")
        osdeps.notify("GitHub Inbox test", "An urgent pop-up, as for a reminder.", urgent=True)
        print("Sent 2 pop-ups: one normal, one urgent.")
