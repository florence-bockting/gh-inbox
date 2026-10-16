"""Command line: gh-inbox daemon | web | stop | tui | sync | test-popup."""

import argparse
import os
import sys
import time
import urllib.request
import webbrowser

from . import db, osdeps, sync, web


def _daemon_up():
    try:
        urllib.request.urlopen(f"http://{web.HOST}:{web.PORT}/api/status", timeout=2)
        return True
    except OSError:
        return False


def _open_browser(url):
    """Open the page. Hide the browser messages: they print after the shell prompt."""
    if osdeps.WINDOWS:
        webbrowser.open(url)
        return
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        webbrowser.open(url)
    finally:
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        for fd in (*saved, devnull):
            os.close(fd)


def cmd_web():
    url = f"http://{web.HOST}:{web.PORT}"
    if not _daemon_up():
        db.DATA_DIR.mkdir(parents=True, exist_ok=True)
        err = db.DATA_DIR / "daemon.err"
        osdeps.start_daemon(err)
        for _ in range(20):
            time.sleep(0.5)
            if _daemon_up():
                break
        else:
            raise SystemExit(f"The daemon did not start. See {err}")
        print("The daemon runs in the background. You can close the terminal.")
        # The executable has its own file name, for example ./gh-inbox-linux.
        name = sys.argv[0] if getattr(sys, "frozen", False) else "gh-inbox"
        print(f"To stop it, run: {name} stop")
    _open_browser(url)


def cmd_stop():
    if not _daemon_up():
        print("The daemon does not run.")
        return
    req = urllib.request.Request(f"http://{web.HOST}:{web.PORT}/api/stop", method="POST",
                                 headers={web.CSRF_HEADER: "1"})
    urllib.request.urlopen(req, timeout=5)
    print("The daemon stopped.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gh-inbox", description="A better GitHub notifications inbox.")
    parser.add_argument("command", choices=["daemon", "web", "stop", "tui", "sync", "test-popup"])
    args = parser.parse_args(argv)
    if args.command == "daemon":
        from . import daemon
        daemon.main()
    elif args.command == "web":
        cmd_web()
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "tui":
        from . import tui
        tui.main()
    elif args.command == "sync":
        print(sync.sync(db.connect()))
    elif args.command == "test-popup":
        osdeps.notify("gh-inbox test", "A normal pop-up.")
        osdeps.notify("gh-inbox test", "An urgent pop-up, as for a reminder.", urgent=True)
        print("Sent 2 pop-ups: one normal, one urgent.")
