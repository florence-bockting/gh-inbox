const TABS = [
  ["action", "Action"], ["watch", "Watch"], ["mine", "My work"], ["todo", "ToDo"],
  ["repos", "Repos"], ["settings", "Settings"],
];
const REASONS = {
  review_requested: "review request", mention: "mention", team_mention: "team mention",
  assign: "assigned", todo: "todo", new_issue: "new issue", new_pr: "new PR", author: "your item",
  comment: "comment", subscribed: "subscribed", state_change: "state change",
  ci_activity: "CI", manual: "subscribed", security_alert: "security",
};
const KINDS = {pr: "PR", issue: "Issue", other: "Other"};
const svg = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
  stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
/* Lucide icons (https://lucide.dev), ISC License:
Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of
Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE. */
const ICONS = {
  github: svg(`<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>`),
  mountain: svg(`<path d="m8 3 4 8 5-5 5 15H2L8 3z"/>`),
  note: svg(`<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h5"/>`),
  done: svg(`<path d="M5 12.5l4.5 4.5L19 7.5"/>`),
  // alarm-clock, octagon-x and ellipsis come from Lucide v0.460.0. See the license below.
  alarmClock: svg(`<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M5 3 2 6"/><path d="m22 6-3-3"/><path d="M6.38 18.7 4 21"/><path d="M17.64 18.67 20 21"/>`),
  octagonX: svg(`<path d="m15 9-6 6"/><path d="M2.586 16.726A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2h6.624a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586z"/><path d="m9 9 6 6"/>`),
  ellipsis: svg(`<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>`),
  undo: svg(`<path d="M4 9h11a5 5 0 0 1 0 10H9"/><path d="M8 5L4 9l4 4"/>`),
};
// A Codeberg repo has the host as prefix: "codeberg.org/owner/repo". GitHub: "owner/repo".
const forgeHost = (repo) => { const p = String(repo).split("/"); return p.length === 3 ? p[0] : null; };
// GH for GitHub, CB for Codeberg, FJ for another Forgejo server.
const forgePrefix = (repo) => !forgeHost(repo) ? "GH" : forgeHost(repo) === "codeberg.org" ? "CB" : "FJ";
const repoName = (repo) => forgePrefix(repo) + " " +
  (forgeHost(repo) ? String(repo).split("/").slice(1).join("/") : repo);
const GITHUB_ICON = `<span class="forge github" title="GitHub">${ICONS.github}</span>`;
const codebergIcon = (title) => `<span class="forge codeberg" title="${esc(title)}">${ICONS.mountain}</span>`;
const forgeIcon = (repo) => forgeHost(repo) ? codebergIcon(forgeHost(repo)) : GITHUB_ICON;
// Filters per tab: [field, label of the "all" option, label of one value].
const FILTER_FIELDS = {
  action: ["provider", "repo", "kind", "reason"], watch: ["provider", "repo", "kind"],
  mine: ["provider", "repo", "kind"], todo: ["provider", "repo", "kind"],
};
const FIELD_LABELS = {
  provider: ["All platforms", (v) => v],
  repo: ["All repos", repoName], kind: ["All kinds", (v) => KINDS[v] || v],
  reason: ["All types", (v) => REASONS[v] || v],
};
let tab = location.hash.slice(1) || "action";
let filters = {action: {}, watch: {}, mine: {}, todo: {}};
let hideStalled = false;
let onlyWaiting = false;
const openMenus = new Set();  // "key|category" of the rows with open options
const selected = new Set();  // "key|category" of the selected rows
let oldest = {action: false, watch: false, mine: false, todo: false};
let status = {};
let lastItems = [];  // The items of the tab, before the filters
let toastUndo = null;
let toastTimer;

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

async function get(path) {
  const r = await fetch(path);
  return r.json();
}
async function post(path, body = {}) {
  const r = await fetch(path, {
    method: "POST", headers: {"Content-Type": "application/json", "X-OSS-Inbox": "1"},
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function ago(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 3600) return Math.max(1, Math.round(s / 60)) + " min ago";
  if (s < 86400) return Math.round(s / 3600) + " h ago";
  return Math.round(s / 86400) + " d ago";
}

const tabLabel = (id) => TABS.find(([i]) => i === id)[1];
const moveOptions = (from) => TABS.slice(0, 4).filter(([id]) => id !== from)
  .map(([id, label]) => `<option value="${id}">${label}</option>`).join("");
// "key|category". The key can contain "|", the category cannot.
const splitId = (id) => { const i = id.lastIndexOf("|"); return [id.slice(0, i), id.slice(i + 1)]; };

// A message at the bottom of the page. With `undo`, it has an Undo button.
// It closes after 8 s. The pointer or the focus on it stops the time.
function showToast(text, undo) {
  clearTimeout(toastTimer);
  toastUndo = undo || null;
  $("#toast").innerHTML = `<span>${esc(text)}</span>` +
    (undo ? `<button class="btn" id="undo">Undo</button>` : "");
  toastTimer = setTimeout(hideToast, 8000);
}
function hideToast() {
  clearTimeout(toastTimer);
  toastUndo = null;
  $("#toast").innerHTML = "";
}
for (const ev of ["mouseenter", "focusin"])
  $("#toast").addEventListener(ev, () => clearTimeout(toastTimer));
for (const ev of ["mouseleave", "focusout"])
  $("#toast").addEventListener(ev, () => { if (toastUndo) toastTimer = setTimeout(hideToast, 8000); });

// The error stays until the user closes it. A render does not remove it.
function showError(text) {
  $("#errors").innerHTML = `<span>${esc(text)}</span><button class="btn" id="closeError">Close</button>`;
}

const shortcutsOn = () => { try { return localStorage.getItem("shortcuts") !== "off"; } catch { return true; } };

// A render replaces the list. These two keep the focus on the same row and control.
// If the row left the list, the focus goes to the row that took its place.
function focusState() {
  const el = document.activeElement;
  if (!el || !el.closest || !el.closest("#main")) return null;
  const row = el.closest(".row[data-row]");
  if (!row) return el.id ? {selector: "#" + el.id}
    : el.dataset.ffield ? {selector: `[data-ffield="${el.dataset.ffield}"]`} : null;
  const rows = [...document.querySelectorAll(".row[data-row]")];
  const control = ["done", "note", "more", "prio", "sel"].find((a) => el.dataset[a] !== undefined);
  return {row: row.dataset.row, index: rows.indexOf(row), control};
}
function restoreFocus(state) {
  if (!state) return;
  if (state.selector) { const el = $(state.selector); if (el) el.focus(); return; }
  const rows = [...document.querySelectorAll(".row[data-row]")];
  const row = rows.find((r) => r.dataset.row === state.row) || rows[Math.min(state.index, rows.length - 1)];
  if (!row) return;
  (state.control && row.querySelector(`[data-${state.control}]`) || row).focus();
}

function setTab(id) {
  tab = id;
  location.hash = id;
  selected.clear();
  return render();
}

function renderTabs() {
  const c = status.counts || {};
  $("#tabs").innerHTML = TABS.map(([id, label]) =>
    `<button role="tab" data-tab="${id}" aria-selected="${id === tab}" tabindex="${id === tab ? 0 : -1}"
      class="${id === tab ? "active" : ""}">${label}` +
    (c[id] ? `<span class="count">${c[id]}</span>` : "") + `</button>`).join("");
}

function renderStatus() {
  const parts = [];
  if (status.login) parts.push(GITHUB_ICON + "@" + esc(status.login));
  if (status.forgejo_login) parts.push(codebergIcon("Codeberg") + "@" + esc(status.forgejo_login));
  parts.push(status.last_sync ? "synced " + ago(status.last_sync) : "never synced");
  parts.push(status.poller_running ? "poller running"
             : `<span class="bad">poller not running</span>`);
  if (status.last_error) parts.push(`<span class="bad" title="${esc(status.last_error)}">sync error</span>`);
  const r = status.rate || {};
  if (r.limit) {
    const api = `API ${r.remaining}/${r.limit}`;
    parts.push(r.level === "ok" ? api : `<span class="bad">${api}</span>`);
  }
  $("#status").innerHTML = parts.join(" · ");
  $("#banner").textContent =
    r.level === "paused" ? `Sync paused: only ${r.remaining} of ${r.limit} GitHub API requests left. ` +
                           `The sync starts again at ${r.reset_clock}. Watch fewer repos, or sync less often.`
    : r.level === "low" ? `Few GitHub API requests left: ${r.remaining} of ${r.limit} until ${r.reset_clock}. ` +
                          `The sync pauses below 10%.` : "";
}

function itemRow(it) {
  const ref = it.number ? `${repoName(it.repo)}#${it.number}` : repoName(it.repo);
  const kind = it.state === "draft" ? "Draft PR" : KINDS[it.kind] || it.kind;
  const badges = [`<span class="badge kind kind-${esc(it.kind)}">${esc(kind)}</span>`];
  if (it.tab !== "mine")
    badges.push(`<span class="badge ${esc(it.reason)}">${esc(REASONS[it.reason] || it.reason)}</span>`);
  if (it.assigned && it.reason !== "assign")
    badges.push(`<span class="badge assign">${REASONS.assign}</span>`);
  // The meta line shows the secondary states. The title keeps only the main ones.
  const metaBadges = [];
  if (it.stalled) metaBadges.push(`<span class="badge stalled">stalled</span>`);
  if (it.review_waits) {
    // The tooltip names the reviewers and their wait time.
    const waits = JSON.parse(it.review_waits);
    const tip = Object.entries(waits).map(([n, t]) =>
      `@${n}: ${Math.floor((Date.now() - Date.parse(t)) / 86400000)}d`).join(", ");
    badges.push(it.waiting_for
      ? `<span class="badge overdue" title="${esc(tip)}">review overdue</span>`
      : `<span class="badge in_review" title="${esc(tip)}">in review</span>`);
  }
  if (it.activity) metaBadges.push(`<span class="badge activity">new activity</span>`);
  if (["action", "todo"].includes(it.tab) && it.notify_count > 1)
    metaBadges.push(`<span class="badge reminded">reminded ${it.notify_count - 1}×</span>`);
  if (it.state && !["open", "draft"].includes(it.state)) badges.push(`<span class="badge">${esc(it.state)}</span>`);
  const when = it.tab === "mine" ? "updated " + ago(it.updated_at) : ago(it.event_at);
  const key = esc(it.key), cat = esc(it.category);
  // Pop-ups follow the tab that shows the item. Stalled pop-ups need a My work item.
  const ownMine = it.tab === "mine" && it.category === "mine";
  let controls = "";
  if (it.tab === "action" || it.tab === "todo" || ownMine) {
    const hours = it.remind_hours ?? "";
    const ph = it.tab === "mine" ? "off" : status.settings.default_remind_hours;
    controls += `<label class="icon" title="Remind every N hours">${ICONS.alarmClock}</label><input type="number" min="0" step="any"
      title="Remind every N hours" aria-label="Remind every N hours"
      data-remind="${key}" data-cat="${cat}" value="${hours}" placeholder="${ph}"><label>h</label>`;
  }
  if (ownMine) {
    controls += `<label class="icon" title="Stalled after N days">${ICONS.octagonX}</label><input type="number" min="0" step="any"
      title="Stalled after N days" aria-label="Stalled after N days"
      data-stall="${key}" value="${it.stall_days ?? ""}" placeholder="${status.settings.stall_days}"><label>d</label>`;
  }
  controls += `<select data-move="${key}" data-cat="${cat}"><option value="">Move to…</option>
    ${moveOptions(it.tab)}</select>`;
  // The reminder, the stall time and the move hide behind the "more" button.
  const menu = esc(it.key + "|" + it.category);
  controls = `<span class="more" data-menu="${menu}" ${openMenus.has(it.key + "|" + it.category) ? "" : "hidden"}>${controls}</span>`;
  // Visible order: done, note, more. The options open on the left: the buttons stay in place.
  const doneLabel = it.done ? "Undo done" : "Mark done";
  controls += `<button class="btn icon" data-done="${key}" data-cat="${cat}" data-val="${it.done ? 0 : 1}"
    title="${doneLabel}" aria-label="${doneLabel}">${it.done ? ICONS.undo : ICONS.done}</button>`;
  const noteLabel = it.note ? "Edit the note" : "Add a note";
  controls += `<button class="btn icon ${it.note ? "has-note" : ""}" data-note="${key}"
    title="${noteLabel}" aria-label="${noteLabel}">${ICONS.note}</button>`;
  controls += `<button class="btn icon" data-more="${menu}" title="More options" aria-label="More options">${ICONS.ellipsis}</button>`;
  const flagLabel = it.priority ? "Unpin" : "Pin to the top";
  const flag = `<button class="flag" data-prio="${key}" data-cat="${cat}" data-val="${it.priority ? 0 : 1}"
    title="${flagLabel}" aria-label="${flagLabel}">${it.priority ? "⚑" : "⚐"}</button>`;
  const check = `<label class="sel" title="Select"><input type="checkbox" data-sel="${menu}"
    aria-label="Select" ${selected.has(it.key + "|" + it.category) ? "checked" : ""}></label>`;
  return `<div class="row ${it.done ? "done" : ""} ${it.priority ? "high" : ""}"
    data-row="${menu}" tabindex="-1">
    <div><div class="title">${check}${flag}${badges.join("")}<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a></div>
    <div class="meta">${forgeIcon(it.repo)}${esc(ref)} · ${it.author ? "by " + esc(it.author) + " · " : ""}${when}${metaBadges.join("")}</div>
    ${it.note ? `<div class="note" title="${esc(it.note)}">${esc(it.note)}</div>` : ""}</div>
    <div class="controls">${controls}</div>
    <div class="note-edit" data-editor="${key}" hidden>
      <textarea rows="3" placeholder="Note. Ctrl+Enter saves. Empty deletes the note.">${esc(it.note)}</textarea>
      <button class="btn primary" data-save-note="${key}">Save</button>
      <button class="btn" data-cancel-note="${key}">Cancel</button></div></div>`;
}

async function renderItems() {
  const items = await get(`/api/items?category=${tab}&done=${$("#showDone").checked ? 1 : 0}` +
                          `&order=${oldest[tab] ? "asc" : "desc"}`);
  lastItems = items;
  const fields = FILTER_FIELDS[tab] || [];
  const chosen = filters[tab] || {};
  const shown = items.filter((i) => fields.every((f) => !chosen[f] || i[f] === chosen[f])
    && !(tab === "mine" && hideStalled && i.stalled)
    && !(tab === "mine" && onlyWaiting && !i.waiting_for));
  // A bulk action applies only to the rows that the list shows.
  const ids = new Set(shown.map((i) => i.key + "|" + i.category));
  for (const id of [...selected]) if (!ids.has(id)) selected.delete(id);
  let toolbar = !selected.size ? "" : `<span class="bulk"><b>${selected.size} selected</b>
    <button class="btn" id="bulkDone">Mark done</button>
    <select id="bulkMove" aria-label="Move the selected items"><option value="">Move to…</option>${moveOptions(tab)}</select>
    <button class="btn" id="clearSel">Clear selection</button></span>`;
  // Offer only the values that occur in the current items. Keep the chosen one listed.
  toolbar += fields.map((field) => {
    const [all, label] = FIELD_LABELS[field];
    const values = [...new Set(items.map((i) => i[field]).filter(Boolean)
      .concat(chosen[field] ? [chosen[field]] : []))].sort();
    return `<select data-ffield="${field}"><option value="">${all}</option>` + values.map((v) =>
      `<option value="${esc(v)}" ${v === chosen[field] ? "selected" : ""}>${esc(label(v))}</option>`).join("") +
      `</select>`;
  }).join("");
  if (tab === "mine")
    toolbar += `<label><input type="checkbox" id="hideStalled" ${hideStalled ? "checked" : ""}> Hide stalled</label>` +
      `<label><input type="checkbox" id="onlyWaiting" ${onlyWaiting ? "checked" : ""}> Review overdue</label>`;
  if (fields.some((f) => chosen[f]) || (tab === "mine" && (hideStalled || onlyWaiting)))
    toolbar += `<button class="btn" id="clearFilters">Clear filters</button>`;
  toolbar += `<button class="btn" id="order" title="Reverse the order">${oldest[tab] ? "↑ Oldest first" : "↓ Newest first"}</button>`;
  if (tab === "watch") toolbar += `<span class="grow"></span><button class="btn" id="allDone">Mark all done</button>`;
  const hint = !status.watched && tab !== "mine"
    ? `<div class="empty">You watch no repos yet. Open the <b>Repos</b> tab and select some.</div>` : "";
  const focus = focusState();
  $("#main").innerHTML = `<div class="toolbar">${toolbar}</div>` + (hint ||
    `<div class="list">${shown.map(itemRow).join("") || `<div class="empty">Nothing here.</div>`}</div>`);
  restoreFocus(focus);
}

// Run one action on each selected row. The toast offers to undo it.
async function bulkApply(path, make, undo, message) {
  const rows = [...selected].map(splitId);
  selected.clear();
  for (const [key, category] of rows) await post(path, make(key, category));
  showToast(message(rows.length), async () => {
    for (const [key, category] of rows) await post(path, undo(key, category));
  });
  return render();
}

async function renderRepos() {
  const repos = await get("/api/repos");
  $("#main").innerHTML = `<div class="toolbar">
      <input id="newRepo" placeholder="owner/repo or Codeberg URL">
      <button class="btn" id="addRepo">Add and watch</button>
      <button class="btn" id="loadRepos">Load my repos</button>
      <span class="grow"></span><input id="repoFilter" placeholder="Filter">
    </div><div class="error" id="repoError"></div>
    <div class="list" id="repoList">${repos.map((r) => `<div class="row" data-name="${esc(r.full_name.toLowerCase())}">
      <div><label><input type="checkbox" data-watch="${esc(r.full_name)}" ${r.watched ? "checked" : ""}>
      ${forgeIcon(r.full_name)}<b>${esc(repoName(r.full_name))}</b></label><div class="meta">${esc(r.source || "")}${r.watch_since ? " · watched since " + ago(r.watch_since) : ""}</div></div>
      <div></div></div>`).join("") || `<div class="empty">No repos yet. Add one, or load your repos.</div>`}</div>`;
}

function renderSettings() {
  const s = status.settings;
  const limit = (status.rate && status.rate.limit) || 5000;
  const field = (key, label, help) => `<label for="set-${key}">${label}</label>
    <input type="number" min="0" step="any" id="set-${key}" data-setting="${key}" value="${esc(s[key])}">
    <span class="help">${help}</span>`;
  // Each service has one card with the same rows: account, server, login.
  const account = (icon, name, login, rows) => `<section class="account">
    <h3>${icon}${name}</h3>
    <div class="settings">
      <span>Account</span>
      <span class="wide ${login ? "connected" : "help"}">${login ? "Connected as @" + esc(login) : "Not connected"}</span>
      ${rows}
    </div></section>`;
  $("#main").innerHTML = `<div class="accounts">
    ${account(GITHUB_ICON, "GitHub", status.login, `
      <span>Server</span><span class="wide">github.com</span>
      <span>Login</span>
      <span class="wide">Run <kbd>gh auth login</kbd> in a terminal.</span>
      <span></span><span class="help wide">The app uses the login of the GitHub CLI. It does not save a GitHub token.</span>
      <span>API use</span>
      <span class="wide ${status.estimate_per_hour > 0.8 * limit ? "error" : "help"}">
        At most about <b>${status.estimate_per_hour}</b> requests each hour
        with ${status.watched} watched repos (limit ${limit}).
        ${status.last_sync_cost != null ? `The last sync used ${esc(status.last_sync_cost)}.` : ""}
        Unchanged repos cost nothing, because GitHub does not count an ETag answer "304".</span>`)}
    ${account(codebergIcon("Codeberg"), "Codeberg", status.forgejo_login, `
      <label for="set-forgejo_url">Server</label>
      <input type="text" class="wide" id="set-forgejo_url" data-setting="forgejo_url" value="${esc(s.forgejo_url)}">
      <span></span><span class="help wide">Codeberg, or another Forgejo server. Apply saves a change.</span>
      <label for="forgejoToken">Login</label>
      <span class="wide token"><input type="password" id="forgejoToken" autocomplete="off"
        placeholder="${status.forgejo_token ? "token saved · type a new one to replace it" : "paste an access token"}">
        <button class="btn" id="saveToken">Save token</button>
        ${status.forgejo_token ? `<button class="btn" id="removeToken">Remove token</button>` : ""}</span>
      <span></span><span class="help wide">Create the token on the server under Settings → Applications.
        Give it read access to notification, issue, repository and user.
        The app saves it in a file that only you can read. Without a token, the app syncs GitHub only.</span>
      <span></span><span class="wide"><span class="help" id="tokenNote"></span><span class="error" id="tokenError"></span></span>`)}
  </div>
  <h3 class="settings-title">General</h3>
  <div class="settings">
    ${field("stall_days", "Stalled after (days)", "Your issue or PR counts as stalled after this many days without activity. Each item can override it. 0 turns it off.")}
    ${field("review_wait_days", "Review wait (days)", "Your PR shows \"in review\" while a review is pending, and \"review overdue\" after this many days. A new request, or your comment that tags @x, starts the time again. 0 turns it off.")}
    ${field("default_remind_hours", "Remind every (hours)", "Default reminder interval for new action items. Each item can override it. 0 turns reminders off.")}
    ${field("poll_minutes", "Sync every (minutes)", "How often the poller asks GitHub and Codeberg for changes.")}
    ${field("new_item_days", "Watch history (days)", "When you start to watch a repo, show its issues and PRs from this many days back.")}
    ${field("notify", "Pop-ups on (1) or off (0)", "Desktop pop-ups from the poller.")}
    <label for="set-notes_file">Notes file</label>
    <input type="text" class="wide" id="set-notes_file" data-setting="notes_file" value="${esc(s.notes_file)}">
    <span></span><span class="help wide">The CSV file with your notes. A change moves the file. The app refuses if a file exists at the new path.</span>
    <label for="shortcutsOn">Keyboard shortcuts</label>
    <span><input type="checkbox" id="shortcutsOn" ${shortcutsOn() ? "checked" : ""}></span>
    <span class="help">Single keys: j and k move between rows. Press ? for the list.
      The change applies at once. This browser keeps it, not the app.</span>
  </div><div class="settings-actions">
    <button class="btn primary" id="applySettings" disabled>Apply</button>
    <button class="btn" id="resetSettings">Reset to defaults</button>
    <span class="help" id="setNote"></span>
  </div><div class="error" id="setError"></div>`;
}

// The settings whose input differs from the saved value.
function changedSettings() {
  const out = {};
  for (const el of document.querySelectorAll("[data-setting]")) {
    if (el.value !== String(status.settings[el.dataset.setting])) out[el.dataset.setting] = el.value;
  }
  return out;
}

function updateApply() {
  $("#applySettings").disabled = !Object.keys(changedSettings()).length;
  $("#setNote").textContent = "";
}

async function applySettings() {
  try {
    await post("/api/settings", changedSettings());
    await render();
    $("#setNote").textContent = "Applied.";
  } catch (err) {
    // Keep the inputs. Compare them with what the server saved before the error.
    status = await get("/api/status");
    updateApply();
    $("#setError").textContent = err.message;
  }
}

async function render() {
  status = await get("/api/status");
  renderTabs();
  renderStatus();
  if (tab === "repos") return renderRepos();
  if (tab === "settings") return renderSettings();
  return renderItems();
}

document.addEventListener("click", (e) => onClick(e).catch((err) => showError(err.message)));

async function onClick(e) {
  const t = e.target;
  // A click on the count reaches the span, not the tab button.
  const tabButton = t.closest("[data-tab]");
  if (tabButton) return setTab(tabButton.dataset.tab);
  if (t.id === "closeError") { $("#errors").innerHTML = ""; return; }
  if (t.id === "undo") {
    const undo = toastUndo;
    hideToast();
    if (undo) await undo();
    return render();
  }
  if (t.id === "bulkDone")
    return bulkApply("/api/items/done", (key, category) => ({key, category, done: true}),
      (key, category) => ({key, category, done: false}), (n) => `${n} marked done.`);
  if (t.id === "clearSel") { selected.clear(); return render(); }
  if (t.id === "order") { oldest[tab] = !oldest[tab]; return render(); }
  if (t.id === "clearFilters") {
    filters[tab] = {};
    if (tab === "mine") hideStalled = onlyWaiting = false;
    return render();
  }
  if (t.dataset.prio) {
    await post("/api/items/priority", {key: t.dataset.prio, category: t.dataset.cat, high: t.dataset.val === "1"});
    return render();
  }
  if (t.dataset.more) {
    const open = !openMenus.delete(t.dataset.more);
    if (open) openMenus.add(t.dataset.more);
    [...document.querySelectorAll(".more")].find((m) => m.dataset.menu === t.dataset.more).hidden = !open;
    return;
  }
  if (t.dataset.note || t.dataset.cancelNote) {
    const box = [...document.querySelectorAll(".note-edit")]
      .find((b) => b.dataset.editor === (t.dataset.note || t.dataset.cancelNote));
    box.hidden = !!t.dataset.cancelNote || !box.hidden;
    if (!box.hidden) box.querySelector("textarea").focus();
    return;
  }
  if (t.dataset.saveNote) return saveNote(t.closest(".note-edit"));
  if (t.dataset.done) {
    const item = {key: t.dataset.done, category: t.dataset.cat};
    const done = t.dataset.val === "1";
    await post("/api/items/done", {...item, done});
    if (done) showToast("Marked done.", () => post("/api/items/done", {...item, done: false}));
    return render();
  }
  if (t.id === "allDone") {
    // The undo restores the items of the tab, also the ones that a filter hides.
    const open = lastItems.filter((i) => !i.done).map((i) => ({key: i.key, category: i.category}));
    await post("/api/items/all-done", {category: "watch"});
    showToast(`${open.length} marked done.`, async () => {
      for (const item of open) await post("/api/items/done", {...item, done: false});
    });
    return render();
  }
  if (t.id === "addRepo") {
    try { await post("/api/repos/add", {full_name: $("#newRepo").value}); render(); }
    catch (err) { $("#repoError").textContent = err.message; }
  }
  if (t.id === "loadRepos") {
    t.disabled = true; t.textContent = "Loading…";
    try { await post("/api/repos/load"); render(); }
    catch (err) { $("#repoError").textContent = err.message; t.disabled = false; }
  }
  if (t.id === "saveToken" || t.id === "removeToken") {
    try {
      await post("/api/forgejo/token", {token: t.id === "saveToken" ? $("#forgejoToken").value : ""});
      await render();
      $("#tokenNote").textContent = t.id === "saveToken" ? "Token saved." : "Token removed.";
    } catch (err) { $("#tokenError").textContent = err.message; }
    return;
  }
  if (t.id === "resetSettings") {
    for (const el of document.querySelectorAll("[data-setting]")) el.value = status.defaults[el.dataset.setting];
    return updateApply();
  }
  if (t.id === "applySettings") return applySettings();
  if (t.id === "stopDaemon"
      && confirm("Stop the daemon? Sync and pop-ups stop until you run oss-inbox web again.")) {
    try { await post("/api/stop"); }
    catch (err) { return showError(err.message); }
    return showStopped();
  }
  if (t.id === "sync") {
    t.disabled = true; t.textContent = "Syncing…";
    try { const r = await post("/api/sync"); if (r.result !== "ok") showError("Sync: " + r.result); }
    finally { t.disabled = false; t.textContent = "Sync now"; render(); }
  }
}

document.addEventListener("change", async (e) => {
  const t = e.target;
  try {
    if (t.dataset.watch) await post("/api/repos/watch", {full_name: t.dataset.watch, watched: t.checked});
    else if (t.dataset.remind) await post("/api/items/remind", {key: t.dataset.remind, category: t.dataset.cat, hours: t.value});
    else if (t.dataset.stall) await post("/api/items/stall", {key: t.dataset.stall, days: t.value});
    else if (t.dataset.move) {
      if (!t.value) return;
      const item = {key: t.dataset.move, category: t.dataset.cat}, from = tab;
      await post("/api/items/move", {...item, to: t.value});
      showToast(`Moved to ${tabLabel(t.value)}.`, () => post("/api/items/move", {...item, to: from}));
    }
    else if (t.id === "bulkMove") {
      if (!t.value) return;
      const to = t.value, from = tab;
      return bulkApply("/api/items/move", (key, category) => ({key, category, to}),
        (key, category) => ({key, category, to: from}), (n) => `${n} moved to ${tabLabel(to)}.`);
    }
    else if (t.dataset.sel) {
      if (t.checked) selected.add(t.dataset.sel); else selected.delete(t.dataset.sel);
      return render();
    }
    else if (t.id === "shortcutsOn") {
      try { localStorage.setItem("shortcuts", t.checked ? "on" : "off"); } catch { /* not saved */ }
      return;
    }
    else if (t.id === "showDone") return render();
    else if (t.dataset.ffield) { filters[tab][t.dataset.ffield] = t.value; return render(); }
    else if (t.id === "hideStalled") { hideStalled = t.checked; return render(); }
    else if (t.id === "onlyWaiting") { onlyWaiting = t.checked; return render(); }
    else return;
    status = await get("/api/status"); renderTabs();
    if (t.dataset.stall || t.dataset.move) render();
  } catch (err) {
    showError(err.message);
  }
});

async function saveNote(box) {
  try {
    await post("/api/items/note", {key: box.dataset.editor, body: box.querySelector("textarea").value});
    render();
  } catch (err) { showError(err.message); }
}

document.addEventListener("keydown", (e) => {
  const t = e.target;
  const box = t.closest && t.closest(".note-edit");
  if (box && e.key === "Enter" && e.ctrlKey) { e.preventDefault(); saveNote(box); return; }
  // The arrow keys move between the tabs, as in the ARIA tabs pattern.
  if (t.closest && t.closest("[data-tab]") && ["ArrowLeft", "ArrowRight"].includes(e.key)) {
    e.preventDefault();
    const i = TABS.findIndex(([id]) => id === tab) + (e.key === "ArrowRight" ? 1 : TABS.length - 1);
    setTab(TABS[i % TABS.length][0]).then(() => $(`[data-tab="${tab}"]`).focus());
    return;
  }
  // The single-key shortcuts. They do nothing while the user types in a field.
  if (!shortcutsOn() || stopped || e.ctrlKey || e.metaKey || e.altKey || $("#help").open) return;
  if (t.matches && t.matches("input, select, textarea, [contenteditable]")) return;
  const rows = [...document.querySelectorAll(".row[data-row]")];
  const row = document.activeElement && document.activeElement.closest
    && document.activeElement.closest(".row[data-row]");
  const press = (selector) => { const el = row && row.querySelector(selector); if (el) el.click(); };
  if (e.key === "j" || e.key === "k") {
    if (!rows.length) return;
    const i = rows.indexOf(row);
    const next = i < 0 ? 0 : Math.min(Math.max(i + (e.key === "j" ? 1 : -1), 0), rows.length - 1);
    rows[next].focus();
  } else if (e.key === "e") press("[data-done]");
  else if (e.key === "s") press("[data-prio]");
  else if (e.key === "x") press("[data-sel]");
  else if (e.key === "u") { if (toastUndo) $("#undo").click(); }
  else if (e.key === "?") $("#help").showModal();
  else return;
  e.preventDefault();
});

document.addEventListener("input", (e) => {
  if (e.target.dataset.setting) return updateApply();
  if (e.target.id !== "repoFilter") return;
  const q = e.target.value.toLowerCase();
  document.querySelectorAll("#repoList .row").forEach((r) => {
    r.style.display = r.dataset.name.includes(q) ? "" : "none";
  });
});

render();
let stopped = false;
let ticks = 0;

function showStopped() {
  stopped = true;
  document.querySelectorAll("header button, header input").forEach((b) => { b.disabled = true; });
  $("#tabs").innerHTML = $("#main").innerHTML = $("#status").innerHTML = "";
  $("#banner").textContent = "The daemon stopped. To start it again, run oss-inbox web in a terminal.";
}

// Check every 5 s that the daemon runs. When it runs again, reload the page.
// Refresh from the local database every 30 s. This makes no GitHub request.
setInterval(async () => {
  let up = true;
  try { await fetch("/api/status", {method: "HEAD"}); } catch { up = false; }
  if (stopped) { if (up) location.reload(); return; }
  if (!up) return showStopped();
  if (++ticks % 6 === 0
      && !document.querySelector("input:focus, select:focus, textarea:focus, .note-edit:not([hidden])")
      && !Object.keys(changedSettings()).length) render();
}, 5000);
