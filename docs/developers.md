# For developers

## Design

- **Two dependencies:** [Flask](https://flask.palletsprojects.com/) for the web
  page, and [Textual](https://textual.textualize.io/) for the terminal UI.
- **`gh api`** makes every GitHub request.
- **SQLite** in WAL mode holds the state. The daemon, the web page and the
  terminal UI can use it at the same time.
- **Both UIs call the same functions** in `services/actions.py`. They behave the same.
- **One provider for each forge.** The sync, the UIs and the pop-ups know only
  the `Provider` contract in `providers/base.py`. They never import a forge client.

## Files

The code has five layers. A layer imports only the layers below it.

| Layer | Content |
| :-- | :-- |
| `ui/` | The two UIs |
| `services/` | The jobs that the UIs and the daemon share |
| `providers/` | One folder for each forge |
| `core/` | The item rules that every forge uses |
| `storage/` | SQLite, the notes CSV and the token files |

| File | Content |
| :-- | :-- |
| `ossinbox/cli.py` | The `oss-inbox` command |
| `ossinbox/daemon.py` | Timer for sync and pop-ups, plus the web server |
| `ossinbox/osdeps.py` | All code that differs between Linux, macOS and Windows |
| `ossinbox/ui/web.py` | Flask app: JSON API for the web page |
| `ossinbox/ui/static/` | The web page: `index.html`, `app.css` and `app.js` |
| `ossinbox/ui/tui.py` | The terminal UI |
| `ossinbox/services/sync.py` | Runs the sync of each forge in the registry |
| `ossinbox/services/actions.py` | The UI actions and the status that both UIs share |
| `ossinbox/services/reminders.py` | Finds the items that need a pop-up now |
| `ossinbox/providers/base.py` | The `Provider` contract and the repo name helpers |
| `ossinbox/providers/registry.py` | The list of forges, and the lookup of a forge by repo name |
| `ossinbox/providers/github/client.py` | Wrapper for `gh api`, with ETags. Only GET requests. |
| `ossinbox/providers/github/sync.py` | Gets data from GitHub and sorts it into the tabs |
| `ossinbox/providers/github/ratelimit.py` | The GitHub rate limit and the cost estimate |
| `ossinbox/providers/forgejo/client.py` | Small client for the Forgejo API. Only GET requests. |
| `ossinbox/providers/forgejo/sync.py` | Gets data from Codeberg and sorts it into the tabs |
| `ossinbox/core/items.py` | Insert, reopen and close items. The stalled flag. |
| `ossinbox/core/timeutil.py` | UTC times as ISO strings |
| `ossinbox/storage/db.py` | SQLite schema, settings and queries |
| `ossinbox/storage/etags.py` | The stored ETags. No HTTP. |
| `ossinbox/storage/notes.py` | Reads and writes the notes CSV |
| `ossinbox/storage/secrets.py` | The token files. Only you can read them. |

## Add a forge

1. Add the folder `providers/<forge>/` with a `client.py` and a `sync.py`.
2. Raise a subclass of `ProviderError` in the client.
3. Use `upsert`, `reopen_item` and `auto_done` from `core/items.py` in the sync.
   Do not write your own item rules.
4. Add a provider class in `providers/<forge>/__init__.py`. Give it every member
   of `Provider` in `providers/base.py`.
5. Add an instance of the class to `PROVIDERS` in `providers/registry.py`.

A repo name must tell its forge. GitHub has "owner/repo". Another forge has
"host/owner/repo". Do not change this format: the database keys use it.

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
Action and in My work at the same time. A sync changes only the fields.
Your own values stay: done, reminder interval, stall time, pin and tab.

## Rules

- **Do not write to a forge.** The clients send only GET requests. Keep it that way.
- **Keep OS-specific code in `osdeps.py`.**
- **Never put text into a script.** Issue titles go to the pop-up tools
  as arguments or environment variables. Then a title cannot run code.
- **Keep the web server safe.** It binds `127.0.0.1` only. It refuses a foreign
  `Host` header. Each POST needs the header `X-OSS-Inbox: 1`.

## Run the tests

Install the developer tools:

```bash
.venv/bin/pip install -e ".[dev]"
```

Run the checks. CI runs the same checks on Linux, macOS and Windows:

```bash
.venv/bin/ruff check ossinbox tests
.venv/bin/pytest -q tests
.venv/bin/pip-audit --skip-editable
```

The page sends a `Content-Security-Policy` header that blocks inline scripts and
styles. Put new JavaScript in `app.js`. Put new CSS in `app.css`.

## Run your changes

`uv tool install .` copies the code. A change in the folder then has no effect on
the `oss-inbox` command. Install the command as editable. It then runs the code in
the folder:

```bash
uv tool install --force --editable .
```

You can have two `oss-inbox` commands: `.venv/bin/oss-inbox` and the `uv tool` command.
Run `which -a oss-inbox` to see which one comes first in your `PATH`.

A change to a Python file needs a daemon restart:

```bash
oss-inbox stop
oss-inbox web
```

A change to `app.js`, `app.css` or `index.html` needs only a page reload.

## Use test data

Set `OSS_INBOX_DIR` to a new folder. The app then does not touch your real data:

```bash
export OSS_INBOX_DIR=/tmp/oss-inbox-test
oss-inbox sync
```

Use another port when the real daemon runs. Set `web.PORT` in a test script.

## Test the app on another system

The macOS code is not tested. Do these checks on the new system.
Report the OS version, the Python version, and the output of each step.

Use test data for all steps (see [Use test data](#use-test-data)).

1. **Install.** Follow [Install from the source](install.md#install-from-the-source), steps 1 and 2.

2. **Sync.** Run `oss-inbox sync`. The output must be `ok`.

3. **Pop-ups.** Run `oss-inbox test-popup`. Two pop-ups must come.
   - On macOS, the first pop-up can ask for permission.
   - On Windows, the pop-ups come from "Windows PowerShell".

4. **Lock.** The second lock must fail:

   ```bash
   python -c "
   from ossinbox import osdeps
   from ossinbox.storage import db
   p = db.DATA_DIR / 'sync.lock'
   with osdeps.try_lock(p) as a:
       with osdeps.try_lock(p) as b:
           print(a, b)   # must print: True False
   "
   ```

5. **One daemon.** Run `oss-inbox daemon` in 2 terminals. The second must stop
   with "Port 8765 is in use".

6. **Web page.** Open http://127.0.0.1:8765. Watch a repo. Click **Sync now**.
   Items must come.

7. **Terminal UI.** Run `oss-inbox tui`. Press `1`–`6`, `d`, `f` and `x`.

8. **Clean up.** Remove the test data folder.

The daemon writes a log to `daemon.log` in the data folder.

## Test the terminal UI without a screen

Textual can run the UI headless. Example:

```python
import asyncio
from ossinbox.ui.tui import InboxApp

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
