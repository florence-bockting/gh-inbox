# For developers

## Design

- **Two dependencies:** [Flask](https://flask.palletsprojects.com/) for the web
  page, and [Textual](https://textual.textualize.io/) for the terminal UI.
- **`gh api`** makes every GitHub request. The app stores no token.
- **SQLite** in WAL mode holds the state. The daemon, the web page and the
  terminal UI can use it at the same time.
- **Both UIs call the same functions** in `state.py`. They behave the same.

## Files

| File | Content |
| :-- | :-- |
| `ghinbox/gh.py` | Wrapper for `gh api`. Only GET requests. |
| `ghinbox/db.py` | SQLite schema, settings and queries |
| `ghinbox/sync.py` | Gets data from GitHub and sorts it into the tabs |
| `ghinbox/reminders.py` | Finds the items that need a pop-up now |
| `ghinbox/notes.py` | Reads and writes the notes CSV |
| `ghinbox/osdeps.py` | All code that differs between Linux, macOS and Windows |
| `ghinbox/state.py` | The UI actions that both UIs share |
| `ghinbox/daemon.py` | Timer for sync and pop-ups, plus the web server |
| `ghinbox/web.py` | Flask app: JSON API for the web page |
| `ghinbox/static/` | The web page: `index.html`, `app.css` and `app.js` |
| `ghinbox/tui.py` | The terminal UI |
| `ghinbox/cli.py` | The `gh-inbox` command |

## How a sync works

1. **Notifications:** get the unread notifications, and the notifications since
   the last sync. Review requests, mentions and assignments go to **Action**.
   The other notifications go to **Watch**.
2. **Review requests:** the search `review-requested:@me` is the source of
   truth. A request that leaves the search result goes to "done".
3. **Mentions and assignments:** GitHub does not always send a notification.
   The searches `mentions:@me` (recent items only) and `assignee:@me` (all open
   items) find the other items. Then get the issue. Load the comments only when
   the issue changed. Compare your last reply with the last mention.
4. **New items:** get the newest issues and PRs of each watched repo.
5. **My work:** the search `author:@me is:open`. Then compute the stalled flag.

The table `items` has the primary key `(key, category)`. One issue can be in
Action and in My work at the same time. A sync changes only the GitHub fields.
Your own values stay: done, reminder interval, stall time, priority and tab.

## Rules

- **Do not write to GitHub.** `gh.py` sends only GET requests. Keep it that way.
- **Keep OS-specific code in `osdeps.py`.**
- **Never put GitHub text into a script.** Issue titles go to the pop-up tools
  as arguments or environment variables. Then a title cannot run code.
- **Keep the web server safe.** It binds `127.0.0.1` only. It refuses a foreign
  `Host` header. Each POST needs the header `X-GH-Inbox: 1`.

## Run the tests

Install the developer tools:

```bash
.venv/bin/pip install -e ".[dev]"
```

Run the checks. CI runs the same checks on Linux, macOS and Windows:

```bash
.venv/bin/ruff check ghinbox tests
.venv/bin/pytest -q tests
.venv/bin/pip-audit --skip-editable
```

The page sends a `Content-Security-Policy` header that blocks inline scripts and
styles. Put new JavaScript in `app.js`. Put new CSS in `app.css`.

## Run your changes

`uv tool install .` copies the code. A change in the folder then has no effect on
the `gh-inbox` command. Install the command as editable. It then runs the code in
the folder:

```bash
uv tool install --force --editable .
```

You can have two `gh-inbox` commands: `.venv/bin/gh-inbox` and the `uv tool` command.
Run `which -a gh-inbox` to see which one comes first in your `PATH`.

A change to a Python file needs a daemon restart:

```bash
gh-inbox stop
gh-inbox web
```

A change to `app.js`, `app.css` or `index.html` needs only a page reload.

## Use test data

Set `GH_INBOX_DIR` to a new folder. The app then does not touch your real data:

```bash
export GH_INBOX_DIR=/tmp/gh-inbox-test
gh-inbox sync
```

Use another port when the real daemon runs. Set `web.PORT` in a test script.

## Test the app on another system

The macOS code is not tested. Do these checks on the new system.
Report the OS version, the Python version, and the output of each step.

Use test data for all steps (see [Use test data](#use-test-data)).

1. **Install.** Follow [Install from the source](install.md#install-from-the-source), steps 1 and 2.

2. **Sync.** Run `gh-inbox sync`. The output must be `ok`.

3. **Pop-ups.** Run `gh-inbox test-popup`. Two pop-ups must come.
   - On macOS, the first pop-up can ask for permission.
   - On Windows, the pop-ups come from "Windows PowerShell".

4. **Lock.** The second lock must fail:

   ```bash
   python -c "
   from ghinbox import osdeps, db
   p = db.DATA_DIR / 'sync.lock'
   with osdeps.try_lock(p) as a:
       with osdeps.try_lock(p) as b:
           print(a, b)   # must print: True False
   "
   ```

5. **One daemon.** Run `gh-inbox daemon` in 2 terminals. The second must stop
   with "Port 8765 is in use".

6. **Web page.** Open http://127.0.0.1:8765. Watch a repo. Click **Sync now**.
   Items must come.

7. **Terminal UI.** Run `gh-inbox tui`. Press `1`–`6`, `d`, `f` and `x`.

8. **Clean up.** Remove the test data folder.

The daemon writes a log to `daemon.log` in the data folder.

## Test the terminal UI without a screen

Textual can run the UI headless. Example:

```python
import asyncio
from ghinbox.tui import InboxApp

async def main():
    app = InboxApp()
    async with app.run_test(size=(150, 40)) as pilot:
        await pilot.press("3")              # My work
        await pilot.press("t")              # hide stalled
        print(len(app.rows["mine"]))

asyncio.run(main())
```

## Make a release

1. Change `version` in `pyproject.toml`, for example to `0.2.0`.
2. Push to `main`.

When CI passes, the `Release` workflow makes the tag `v0.2.0`. It builds the
executables for Linux, macOS and Windows. Then it attaches them to the release.
When the tag exists, the workflow does nothing.

A tag that you push by hand also starts a release. The tag must match `version`.

## Write the docs

The docs use [MkDocs](https://www.mkdocs.org/) with the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. The pages are in `docs/`.

Install the tools. Then start a preview at http://127.0.0.1:8000:

```bash
.venv/bin/pip install -e ".[docs]"
.venv/bin/mkdocs serve
```

The `Docs` workflow builds the site with `mkdocs build --strict` for each pull
request. A warning, for example a broken link, makes the build fail. A push to
`main` deploys the site to GitHub Pages.
