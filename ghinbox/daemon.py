"""Background process: sync on a timer, send pop-ups, and serve the web page."""

import logging
import sys
import threading
import time

from . import db, reminders, sync, web

TICK_SECONDS = 60


def poll_loop(stop):
    conn = db.connect()
    last_sync = 0.0
    while not stop.is_set():
        db.set_meta(conn, "heartbeat", str(time.time()))
        minutes = db.get_setting(conn, "poll_minutes", float)
        if time.time() - last_sync >= minutes * 60:
            result = sync.sync(conn)
            logging.info("sync: %s", result)
            if result != "busy":
                last_sync = time.time()
        else:
            # Stall times grow without a sync; check them every tick.
            sync.refresh_stalled(conn)
        try:
            sent = reminders.run(conn)
            if sent:
                logging.info("pop-ups for %d items", sent)
        except Exception:
            logging.exception("reminders failed")
        stop.wait(TICK_SECONDS)


def main():
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=db.DATA_DIR / "daemon.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s")
    # Bind the port first: a second daemon then fails here and sends no double pop-ups.
    try:
        server = web.make_server()
    except OSError as exc:
        raise SystemExit(f"Port {web.PORT} is in use. Is the daemon already running? ({exc})")
    stop = threading.Event()
    threading.Thread(target=poll_loop, args=(stop,), daemon=True).start()
    logging.info("daemon started on http://%s:%d", web.HOST, web.PORT)
    if sys.stdout:  # pythonw on Windows has no console
        print(f"GitHub Inbox runs at http://{web.HOST}:{web.PORT}  (Ctrl+C stops it)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
