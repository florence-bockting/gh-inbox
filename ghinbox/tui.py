"""Terminal UI built with Textual. It reads the same database as the web page."""

import webbrowser
from datetime import datetime, timezone

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import (
    Checkbox, DataTable, Footer, Header, Input, Label, Select, Static, TabbedContent, TabPane)

from . import db, state, sync

REASONS = {
    "review_requested": ("review", "bold cyan"), "mention": ("mention", "bold magenta"),
    "team_mention": ("team mention", "magenta"), "assign": ("assigned", "yellow"),
    "todo": ("todo", "bold #5fd0cc"),
    "new_issue": ("new issue", "green"), "new_pr": ("new PR", "green"),
}
REASON_LABELS = {
    "review_requested": "review request", "mention": "mention", "team_mention": "team mention",
    "assign": "assigned", "todo": "todo", "new_issue": "new issue", "new_pr": "new PR", "author": "your item",
    "comment": "comment", "subscribed": "subscribed", "state_change": "state change",
    "ci_activity": "CI", "manual": "subscribed", "security_alert": "security",
}
KINDS = {"pr": ("PR", "bold #b48cf0"), "issue": ("Issue", "bold green"), "other": ("Other", "dim")}
# Filters per tab, and the label of the "all" option of each filter.
FILTER_FIELDS = {
    "action": ["repo", "kind", "reason"], "watch": ["repo", "kind"],
    "mine": ["repo", "kind"], "todo": ["repo", "kind"],
}
FIELD_PROMPTS = {"repo": "All repos", "kind": "All kinds", "reason": "All types"}
FIELD_LABELS = {
    "repo": lambda v: v,
    "kind": lambda v: KINDS.get(v, (v,))[0],
    "reason": lambda v: REASON_LABELS.get(v, v),
}
TABS = [("action", "Action"), ("watch", "Watch"), ("mine", "My work"),
        ("todo", "ToDo"), ("repos", "Repos"), ("settings", "Settings")]
SETTINGS = [
    ("stall_days", "Stalled after (days)"),
    ("review_wait_days", "Review wait (days)"),
    ("default_remind_hours", "Remind every (hours)"),
    ("poll_minutes", "Sync every (minutes)"),
    ("new_item_days", "Watch history (days)"),
    ("notify", "Pop-ups on (1) / off (0)"),
    ("notes_file", "Notes file"),
]


def ago(iso):
    if not iso:
        return ""
    s = (datetime.now(timezone.utc) - db.parse_iso(iso)).total_seconds()
    if s < 3600:
        return f"{max(1, round(s / 60))}m"
    if s < 86400:
        return f"{round(s / 3600)}h"
    return f"{round(s / 86400)}d"


def _ident(row):
    return row.get("key") or row.get("full_name"), row.get("category")


class Prompt(ModalScreen):
    """Ask for one value. Enter returns it; Escape cancels."""

    DEFAULT_CSS = """
    Prompt { align: center middle; }
    Prompt > Vertical { width: 64; height: auto; padding: 1 2; border: round $accent;
                        background: $panel; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, question, value=""):
        super().__init__()
        self.question, self.value = question, value

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.question)
            yield Input(value=self.value)

    def on_input_submitted(self, event):
        self.dismiss(event.value)

    def action_cancel(self):
        self.dismiss(None)


class InboxApp(App):
    TITLE = "GitHub Inbox"
    CSS = """
    #status { height: 1; padding: 0 1; background: $boost; }
    DataTable { height: 1fr; }
    .filters { height: auto; }
    .filters Select { width: 1fr; }
    .filters Checkbox { width: auto; }
    """
    BINDINGS = [
        *[Binding(str(n), f"show_tab('{tab}')", label, show=False)
          for n, (tab, label) in enumerate(TABS, 1)],
        Binding("u", "sync", "Sync"),
        Binding("o,enter", "open", "Open", show=True),
        Binding("d", "done", "Done/undo"),
        Binding("r", "remind", "Remind every"),
        Binding("s", "stall", "Stall days"),
        Binding("m", "move", "Move to tab"),
        Binding("p", "priority", "High priority"),
        Binding("n", "note", "Note"),
        Binding("f", "filter", "Filter"),
        Binding("x", "clear_filters", "Clear filters"),
        Binding("t", "toggle_stalled", "Hide stalled"),
        Binding("w", "toggle_waiting", "Review overdue"),
        Binding("v", "reverse", "Reverse order"),
        Binding("h", "toggle_done", "Show done"),
        Binding("A", "all_done", "All done"),
        Binding("space", "watch", "Watch on/off"),
        Binding("a", "add_repo", "Add repo"),
        Binding("L", "load_repos", "Load repos"),
        Binding("e", "edit_setting", "Edit"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.conn = db.connect()
        self.show_done = False
        self.rows = {}  # tab id -> list of row dicts in table order
        self.filters = {tab: dict.fromkeys(fields) for tab, fields in FILTER_FIELDS.items()}
        self.options = {}  # (tab, field) -> values now offered in the drop-down list
        self.hide_stalled = False
        self.only_waiting = False
        self.oldest = dict.fromkeys(FILTER_FIELDS, False)  # tab -> oldest first

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="status")
        with TabbedContent(initial="action"):
            for tab_id, label in TABS:
                with TabPane(f"{TABS.index((tab_id, label)) + 1} {label}", id=tab_id):
                    if tab_id in FILTER_FIELDS:
                        with Horizontal(classes="filters"):
                            for field in FILTER_FIELDS[tab_id]:
                                yield Select([], prompt=FIELD_PROMPTS[field],
                                             id=f"{tab_id}--{field}", type_to_search=False)
                            if tab_id == "mine":
                                yield Checkbox("Hide stalled", id="hide-stalled")
                                yield Checkbox("Review overdue", id="only-waiting")
                    yield DataTable(id=f"t-{tab_id}", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self):
        self.query_one("#t-action", DataTable).add_columns(
            "Kind", "", "Repo", "Title", "By", "Age", "Remind")
        self.query_one("#t-watch", DataTable).add_columns("Kind", "", "Repo", "Title", "By", "Age")
        self.query_one("#t-todo", DataTable).add_columns(
            "Kind", "", "Repo", "Title", "By", "Age", "Remind")
        self.query_one("#t-mine", DataTable).add_columns(
            "Kind", "", "Repo", "Title", "Updated", "Stall after", "Remind")
        self.query_one("#t-repos", DataTable).add_columns("Watch", "Repo", "Source")
        self.query_one("#t-settings", DataTable).add_columns("Setting", "Value")
        self.refresh_all()
        # Re-read the local database every 30 s. This makes no GitHub request.
        self.set_interval(30, self.refresh_all)

    # ---- helpers ------------------------------------------------------------

    @property
    def tab(self):
        return self.query_one(TabbedContent).active

    def current(self):
        table = self.query_one(f"#t-{self.tab}", DataTable)
        rows = self.rows.get(self.tab, [])
        if not rows or table.cursor_row is None or table.cursor_row >= len(rows):
            return None
        return rows[table.cursor_row]

    def ask(self, question, value, callback):
        self.push_screen(Prompt(question, value), callback)

    def do(self, action, body):
        try:
            state.apply(self.conn, action, body)
        except (KeyError, ValueError) as exc:
            self.notify(str(exc), severity="error")
        self.refresh_all()

    # ---- rendering ----------------------------------------------------------

    def refresh_all(self):
        st = state.status(self.conn)
        parts = [f"@{st['login']}" if st["login"] else "not synced yet",
                 f"synced {ago(st['last_sync'])} ago" if st["last_sync"] else "never synced",
                 "poller running" if st["poller_running"] else "[b red]poller not running[/]"]
        if self.show_done:
            parts.append("showing done")
        rate = st["rate"]
        if rate.get("limit"):
            api = f"API {rate['remaining']}/{rate['limit']}"
            if rate["level"] == "paused":
                api = f"[b red]{api} · sync paused until {rate['reset_clock']}[/]"
            elif rate["level"] == "low":
                api = f"[b yellow]{api} · few requests left[/]"
            parts.append(api)
        if st["last_error"]:
            parts.append(f"[red]error: {st['last_error'][:80]}[/]")
        if not st["watched"]:
            parts.append("[yellow]watch some repos in the Repos tab[/]")
        self.query_one("#status", Static).update(" · ".join(parts))

        tabs = self.query_one(TabbedContent)
        for tab_id, label in TABS[:4]:
            n = st["counts"].get(tab_id, 0)
            number = [t for t, _ in TABS].index(tab_id) + 1
            tabs.get_tab(tab_id).label = f"{number} {label}" + (f" ({n})" if n else "")

        settings = st["settings"]
        self._fill("action", self._items("action"), lambda it: (
            self._kind(it), self._badge(it), it["repo"] + (f"#{it['number']}" if it["number"] else ""),
            self._title(it), it["author"] or "", ago(it["event_at"]),
            f"{it['remind_hours']:g}h" if it["remind_hours"] is not None
            else f"{float(settings['default_remind_hours']):g}h"))
        self._fill("todo", self._items("todo"), lambda it: (
            self._kind(it), self._badge(it), it["repo"] + (f"#{it['number']}" if it["number"] else ""),
            self._title(it), it["author"] or "", ago(it["event_at"]),
            f"{it['remind_hours']:g}h" if it["remind_hours"] is not None
            else f"{float(settings['default_remind_hours']):g}h"))
        self._fill("watch", self._items("watch"), lambda it: (
            self._kind(it), self._badge(it), it["repo"] + (f"#{it['number']}" if it["number"] else ""),
            self._title(it), it["author"] or "", ago(it["event_at"])))
        self._fill("mine", self._items("mine"), lambda it: (
            self._kind(it), self._badge(it), f"{it['repo']}#{it['number']}", self._title(it),
            ago(it["updated_at"]),
            f"{it['stall_days']:g}d" if it["stall_days"] is not None
            else f"{float(settings['stall_days']):g}d (default)",
            f"{it['remind_hours']:g}h" if it["remind_hours"] else "off"))
        self._fill("repos", db.list_repos(self.conn), lambda r: (
            Text("[x]" if r["watched"] else "[ ]", style="bold green" if r["watched"] else ""),
            r["full_name"], r["source"] or ""))
        info = [
            {"key": None, "label": "API requests each hour (most)",
             "value": f"about {st['estimate_per_hour']} of {rate.get('limit', 5000)}"},
            {"key": None, "label": "Last sync used", "value": st["last_sync_cost"] or "?"},
        ]
        self._fill("settings", [{"key": k, "label": l, "value": settings[k]}
                                for k, l in SETTINGS] + info, lambda s: (s["label"], s["value"]))

    def _items(self, category):
        items = db.list_items(self.conn, category, self.show_done, self.oldest.get(category, False))
        if category not in FILTER_FIELDS:
            return items
        self._update_options(category, items)
        for field, value in self.filters[category].items():
            if value:
                items = [i for i in items if i[field] == value]
        if category == "mine" and self.hide_stalled:
            items = [i for i in items if not i["stalled"]]
        if category == "mine" and self.only_waiting:
            items = [i for i in items if i["waiting_for"]]
        return items

    def _update_options(self, tab_id, items):
        """Offer only the values that occur in the current items. Keep the chosen one listed."""
        for field in FILTER_FIELDS[tab_id]:
            chosen = self.filters[tab_id][field]
            values = sorted({i[field] for i in items if i[field]} | ({chosen} if chosen else set()))
            if self.options.get((tab_id, field)) == values:
                continue
            self.options[(tab_id, field)] = values
            select = self.query_one(f"#{tab_id}--{field}", Select)
            select.set_options([(FIELD_LABELS[field](v), v) for v in values])
            if chosen:
                select.value = chosen

    def on_select_changed(self, event):
        tab_id, field = event.select.id.split("--")
        value = event.value if isinstance(event.value, str) else None
        if self.filters[tab_id].get(field) != value:
            self.filters[tab_id][field] = value
            self.refresh_all()

    def on_checkbox_changed(self, event):
        name = "only_waiting" if event.checkbox.id == "only-waiting" else "hide_stalled"
        if getattr(self, name) != event.value:
            setattr(self, name, event.value)
            self.refresh_all()

    def _kind(self, it):
        label, style = KINDS.get(it["kind"], (it["kind"] or "", "dim"))
        if it["state"] == "draft":
            label = "Draft PR"
        text = Text(label, style=style)
        if it["done"]:
            text.stylize("strike dim")
        return text

    def _title(self, it):
        text = Text(it["title"] or "")
        if it.get("waiting_for"):
            text.stylize("bold #f0a070")
        if it.get("note"):
            note = it["note"].splitlines()[0]
            text.append("  ✎ " + (note[:40] + "…" if len(note) > 40 else note), style="dim italic")
        if it["priority"]:
            text = Text("★ ", style="bold red") + text
        return text

    def _badge(self, it):
        if it["tab"] == "mine":
            text = Text()
            if it["stalled"]:
                text.append("stalled ", style="bold red")
            if it["waiting_for"]:
                text.append("review overdue ", style="bold red")
            elif it["review_waits"]:
                text.append("in review ", style="bold #a59cf5")
            if it["activity"]:
                text.append("new activity", style="bold green")
        else:
            label, style = REASONS.get(it["reason"], (it["reason"] or "", "dim"))
            text = Text(label, style=style)
            if it.get("assigned") and it["reason"] != "assign":
                text.append(" " + REASONS["assign"][0], style=REASONS["assign"][1])
        if it["done"]:
            text.stylize("strike dim")
        return text

    def _fill(self, tab_id, rows, cells):
        table = self.query_one(f"#t-{tab_id}", DataTable)
        cursor = table.cursor_row or 0
        old = self.rows.get(tab_id, [])
        ident = _ident(old[cursor]) if cursor < len(old) else None
        table.clear()
        for row in rows:
            table.add_row(*cells(row))
        self.rows[tab_id] = rows
        if rows:
            # Keep the cursor on the same item when the list sorts again.
            idents = [_ident(r) for r in rows]
            index = idents.index(ident) if ident in idents else min(cursor, len(rows) - 1)
            table.move_cursor(row=index)

    # ---- actions ------------------------------------------------------------

    def action_show_tab(self, tab_id):
        self.query_one(TabbedContent).active = tab_id
        self.query_one(f"#t-{tab_id}", DataTable).focus()

    def on_tabbed_content_tab_activated(self, event):
        # Keep the keys working after a tab click: focus the table of the new tab.
        self.query_one(f"#t-{event.pane.id}", DataTable).focus()

    @work(thread=True, exclusive=True)
    def action_sync(self):
        self.call_from_thread(self.notify, "Syncing with GitHub…")
        result = sync.sync(db.connect())
        self.call_from_thread(self.notify, f"Sync: {result}",
                              severity="information" if result == "ok" else "warning")
        self.call_from_thread(self.refresh_all)

    def action_open(self):
        it = self.current()
        if it and it.get("url"):
            webbrowser.open(it["url"])
        elif it and it.get("full_name"):
            webbrowser.open(f"https://github.com/{it['full_name']}")

    def action_done(self):
        it = self.current()
        if it and "category" in it:
            self.do("items/done", {"key": it["key"], "category": it["category"],
                                   "done": not it["done"]})

    def action_priority(self):
        it = self.current()
        if it and "category" in it:
            self.do("items/priority", {"key": it["key"], "category": it["category"],
                                       "high": not it["priority"]})

    def action_note(self):
        it = self.current()
        if not it or "category" not in it:
            return
        self.ask("Note (empty = delete):", it.get("note") or "",
                 lambda v: v is not None and self.do("items/note", {"key": it["key"], "body": v}))

    def action_move(self):
        it = self.current()
        if not it or "category" not in it:
            return
        names = ", ".join(t for t, _ in TABS[:4] if t != it["tab"])
        self.ask(f"Move to tab ({names}):", "",
                 lambda v: v and self.do("items/move", {"key": it["key"],
                                                        "category": it["category"],
                                                        "to": v.strip().lower()}))

    @staticmethod
    def _own_mine(it):
        return it.get("tab") == "mine" and it.get("category") == "mine"

    def action_all_done(self):
        if self.tab == "watch":
            self.do("items/all-done", {"category": "watch"})

    def action_remind(self):
        it = self.current()
        # Pop-ups follow the tab that shows the item. Stalled pop-ups need a My work item.
        if not it or not (it.get("tab") in ("action", "todo") or self._own_mine(it)):
            return
        value = "" if it["remind_hours"] is None else f"{it['remind_hours']:g}"
        self.ask("Remind me every N hours (0 = off, empty = default):", value,
                 lambda v: v is not None and self.do(
                     "items/remind", {"key": it["key"], "category": it["category"], "hours": v}))

    def action_stall(self):
        it = self.current()
        if not it or not self._own_mine(it):
            return
        value = "" if it["stall_days"] is None else f"{it['stall_days']:g}"
        self.ask("Stalled after N days without activity (0 = off, empty = default):", value,
                 lambda v: v is not None and self.do("items/stall", {"key": it["key"], "days": v}))

    def action_filter(self):
        if self.tab in FILTER_FIELDS:
            self.query_one(f"#{self.tab}--repo", Select).focus()

    def action_clear_filters(self):
        if self.tab not in FILTER_FIELDS:
            return
        self.filters[self.tab] = dict.fromkeys(FILTER_FIELDS[self.tab])
        for field in FILTER_FIELDS[self.tab]:
            self.query_one(f"#{self.tab}--{field}", Select).clear()
        if self.tab == "mine":
            self.query_one("#hide-stalled", Checkbox).value = False
            self.query_one("#only-waiting", Checkbox).value = False
        self.refresh_all()

    def action_reverse(self):
        if self.tab in self.oldest:
            self.oldest[self.tab] = not self.oldest[self.tab]
            self.notify("Oldest first" if self.oldest[self.tab] else "Newest first")
            self.refresh_all()

    def action_toggle_stalled(self):
        if self.tab == "mine":
            box = self.query_one("#hide-stalled", Checkbox)
            box.value = not box.value

    def action_toggle_waiting(self):
        if self.tab == "mine":
            box = self.query_one("#only-waiting", Checkbox)
            box.value = not box.value

    def action_toggle_done(self):
        self.show_done = not self.show_done
        self.refresh_all()

    def action_watch(self):
        it = self.current()
        if it and "full_name" in it:
            self.do("repos/watch", {"full_name": it["full_name"], "watched": not it["watched"]})

    def action_add_repo(self):
        self.ask("Add and watch a repo (owner/repo):", "",
                 lambda v: v and self.do("repos/add", {"full_name": v}))

    @work(thread=True, exclusive=True)
    def action_load_repos(self):
        self.call_from_thread(self.notify, "Loading your GitHub repos…")
        try:
            sync.load_repo_candidates(db.connect())
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")
        self.call_from_thread(self.refresh_all)

    def action_edit_setting(self):
        it = self.current()
        if not it or not it.get("key") or "label" not in it:
            return
        value = db.get_setting(self.conn, it["key"])
        self.ask(f"{it['label']}:", value,
                 lambda v: v is not None and self.do("settings", {it["key"]: v}))


def main():
    InboxApp().run()
