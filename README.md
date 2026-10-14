# GitHub Inbox

A local inbox for your GitHub notifications. It separates the items that need
your action from the items that you only want to follow. It reminds you again
when you do not act.

The app uses the [`gh` CLI](https://cli.github.com/) for each GitHub request. It
uses no AI service and no extra token. It sends only read requests, so it never
changes anything on GitHub. All data stays on your computer.

- [For users: set up the app](#for-users-set-up-the-app)
- [For developers: change and test the app](#for-developers-change-and-test-the-app)

---

## For users: set up the app

### What the app shows

| Tab | Content |
| :-- | :-- |
| **Action** | Review requests, @mentions and assignments in the repos that you watch |
| **Watch** | New issues and PRs, and all other notifications, in the repos that you watch. No action is necessary. |
| **My work** | Your open issues and PRs in all repos. An item is "stalled" when it has no activity for N days. A PR shows "in review" while a review is pending, and "review overdue" after N days. |
| **ToDo** | Your own tasks: issues and PRs where you mention yourself, in the repos that you watch. You can also move any item here. |
| **Repos** | The repos that you watch in this app |
| **Settings** | Stall time, review wait, reminder interval, sync interval, pop-ups and the notes file |

Each item has a **PR**, **Issue** or **Draft PR** label. In Action, an item
can have a **mention** tag and an **assigned** tag at the same time. The two tags
have different colors.

You can filter Action, Watch, My work and ToDo by repo and kind. You can also
filter Action by type. In My work, you can also hide the stalled items, or show
only the PRs with an overdue review.

### Icons

Each item has these buttons in the web page.

| Icon | Meaning | Key in the terminal UI |
| :-- | :-- | :-- |
| ☆ / ★ | Give the item high priority, or remove it | `p` |
| <img src="docs/icons/done.svg" height="16" alt="done"> | Mark the item done | `d` |
| <img src="docs/icons/undo.svg" height="16" alt="undo"> | Undo done | `d` |
| <img src="docs/icons/note.svg" height="16" alt="note"> | Add or edit a note. The icon is blue when the item has a note. | `n` |
| <img src="docs/icons/more.svg" height="16" alt="more"> | Show more options: reminder, stall time and **Move to…** | — |
| <img src="docs/icons/reminder.svg" height="16" alt="reminder"> | Remind me every N hours (behind <img src="docs/icons/more.svg" height="16" alt="more">) | `r` |
| <img src="docs/icons/stall.svg" height="16" alt="stall"> | Stalled after N days, in My work (behind <img src="docs/icons/more.svg" height="16" alt="more">) | `s` |

### Priority and tabs

- Click ☆ on an item, or press `p` in the terminal UI. The item gets high
  priority. High-priority items come first in the list.
- Click <img src="docs/icons/more.svg" height="16" alt="more"> on an item. Then use **Move to…**. In the
  terminal UI, press `m`. The item goes to
  Action, Watch, My work or ToDo.
- The pop-ups follow the tab that shows the item. A moved item gives stalled
  pop-ups only when it is your own item in My work.

### Notes

- Click <img src="docs/icons/note.svg" height="16" alt="note"> on an item, or press `n` in the terminal UI. Write the note.
  In the web page, Ctrl+Enter saves it. An empty note deletes it.
- A note belongs to the issue or PR. It shows in every tab with that item.
- The app saves the notes in a CSV file. The default is `~/gh-inbox/notes.csv`.
  You can edit the file by hand. The app reads it again at each page load.
- When you change the "Notes file" setting, the app moves the file. If a file
  exists at the new path, the app refuses.
- The terminal UI shows and edits only the first line of a note. Edit notes
  with more than one line in the web page.

### Reminders

- A new action item or to-do gives a pop-up.
- The pop-up comes again after the reminder interval until you act. The default
  interval is 24 hours. You can set an interval for each item (<img src="docs/icons/reminder.svg" height="16" alt="reminder">). 0 turns the
  reminders off.
- A stalled item gives one pop-up. Set a reminder interval (<img src="docs/icons/reminder.svg" height="16" alt="reminder">) on the item to get
  more.
- A PR with an overdue review gives a pop-up. The pop-up comes again after the
  reminder interval. To start the wait time again, request the review again, or
  tag @x in a comment.
- More than 5 pop-ups at the same time become one summary pop-up.

The app finds out when you act:

- **Review request:** GitHub removes the request when you submit a review. The
  item then goes to "done".
- **Mention:** the item goes to "done" when you reply after the last mention.
  A new mention opens the item again. While you are an assignee, the item
  stays open.
- **To-do:** you mention yourself, for example "@me open a follow-up PR".
  The item goes to ToDo, not to Action. Your later replies do not mark it
  done. Click <img src="docs/icons/done.svg" height="16" alt="done">, or close the item. A newer self-mention opens it again.
- **Assignment:** the item goes to "done" when the issue closes, or when you are
  no longer assigned. A new assignment opens a done item again.

You can also click <img src="docs/icons/done.svg" height="16" alt="done"> yourself. "Done" changes only the app. GitHub still
shows the notification as unread.

### Requirements

| | Linux | macOS | Windows |
| :-- | :-- | :-- | :-- |
| Status | Tested (Ubuntu, GNOME) | Not tested | Not tested |
| Python | 3.10 or later | 3.10 or later | 3.10 or later |
| `gh` CLI | Yes | Yes | Yes |
| Pop-ups | `notify-send` | Built in | Built in |

### Install

1. Install the `gh` CLI. Then log in with your own GitHub account:

   ```bash
   gh auth login
   ```

2. Get the code and install it:

   ```bash
   git clone https://github.com/florence-bockting/gh-inbox.git
   cd gh-inbox
   python3 -m venv .venv
   .venv/bin/pip install -e .
   ```

   On Windows, use `py -m venv .venv` and `.venv\Scripts\pip install -e .`
   In the next steps, use `.venv\Scripts\gh-inbox.exe` in place of
   `.venv/bin/gh-inbox`.

3. Start the app each time you log in:

   ```bash
   .venv/bin/gh-inbox install-autostart
   ```

   The command tells you how to start the app now, without a new login.

4. Open http://127.0.0.1:8765 in your browser.

5. Open the **Repos** tab. Click **Load my GitHub repos**, or type `owner/repo`.
   Then select the repos to watch.

### Use the app

The background process (the "daemon") syncs with GitHub every 5 minutes. It
sends the pop-ups and serves the web page.

| Command | What it does |
| :-- | :-- |
| `gh-inbox daemon` | Starts the background process. Only one can run. |
| `gh-inbox web` | Opens the web page. Starts the daemon if it does not run. |
| `gh-inbox tui` | Opens the terminal UI |
| `gh-inbox sync` | Runs one sync now |
| `gh-inbox test-popup` | Sends 2 test pop-ups |
| `gh-inbox install-autostart` | Starts the daemon at each login |
| `gh-inbox remove-autostart` | Stops the start at login |

Keys in the terminal UI:

| Key | Action |
| :-- | :-- |
| `1`–`6` | Go to a tab |
| `o` or `Enter` | Open the item in the browser |
| `d` | Done, or undo |
| `n` | Write or change the note of the item |
| `r` | Set the reminder interval of the item |
| `s` | Set the stall time of the item (My work) |
| `m` | Move the item to another tab |
| `p` | Give the item high priority, or remove it |
| `f` / `x` | Go to the filters / clear the filters |
| `t` | Hide stalled items (My work) |
| `w` | Show only the PRs with an overdue review (My work) |
| `h` | Show done items |
| `v` | Reverse the order: newest first or oldest first |
| `A` | Mark all Watch items done |
| `Space` | Watch a repo, or stop (Repos) |
| `a` / `L` | Add a repo / load your GitHub repos (Repos) |
| `e` | Edit a setting (Settings) |
| `u` | Sync now |
| `q` | Quit |

### Privacy

- The web page listens only on `127.0.0.1`. Other computers cannot open it.
- The data is in `~/.local/share/gh-inbox/`. Remove this folder to remove all
  data. Your notes are in a different place: the "Notes file" setting.
- The app does not send your notes to GitHub.
- The pop-ups show issue titles. Other people can see them on your screen.

---

## For developers: change and test the app

### Design

- **Python standard library only**, plus [Textual](https://textual.textualize.io/)
  for the terminal UI.
- **`gh api`** makes every GitHub request. The app stores no token.
- **SQLite** in WAL mode holds the state. The daemon, the web page and the
  terminal UI can use it at the same time.
- **Both UIs call the same functions** in `state.py`. They behave the same.

### Files

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
| `ghinbox/web.py` | JSON API for the web page |
| `ghinbox/static/index.html` | The web page (HTML, CSS and JavaScript in one file) |
| `ghinbox/tui.py` | The terminal UI |
| `ghinbox/cli.py` | The `gh-inbox` command |

### How a sync works

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

### Rules

- **Do not write to GitHub.** `gh.py` sends only GET requests. Keep it that way.
- **Keep OS-specific code in `osdeps.py`.**
- **Never put GitHub text into a script.** Issue titles go to the pop-up tools
  as arguments or environment variables. A title can then not run code.
- **Keep the web server safe.** It binds `127.0.0.1` only. It refuses a foreign
  `Host` header. Each POST needs the header `X-GH-Inbox: 1`.

### Use test data

Set `GH_INBOX_DIR` to a new folder. The app then does not touch your real data:

```bash
export GH_INBOX_DIR=/tmp/gh-inbox-test
gh-inbox sync
```

Use another port when the real daemon runs. Set `web.PORT` in a test script.

### Test the app on another system

The macOS and Windows code is not tested. Do these checks on the new system.
Report the OS version, the Python version, and the output of each step.

Use test data for all steps (see [Use test data](#use-test-data)).

1. **Install.** Follow [Install](#install), steps 1 and 2.

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

7. **Terminal UI.** Run `gh-inbox tui`. Press `1`–`5`, `d`, `f` and `x`.

8. **Login start.** Run `gh-inbox install-autostart`. Log out, then log in.
   The web page must show "poller running".
   - On macOS, the file is `~/Library/LaunchAgents/io.github.gh-inbox.plist`.
     Errors go to `~/.local/share/gh-inbox/daemon.err`.
   - On Windows, the file is `gh-inbox.vbs` in the Startup folder.
     No console window may open.

9. **Clean up.** Run `gh-inbox remove-autostart`. Remove the test data folder.

The daemon writes a log to `daemon.log` in the data folder.

### Test the terminal UI without a screen

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
