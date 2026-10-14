# Scenario

This file lists the scenarios that the app must support. A checked box means
that the app supports the scenario now.

| Status | Scenario | Tab |
| :-- | :-- | :-- |
| [x] | 1. I open an issue or a pull request. | Mine |
| [x] | 2. Someone mentions me, assigns an item to me, or requests my review. | Action |
| [x] | 3. I watch the new issues and pull requests in specific repos. | Watch |
| [x] | 4. I mention myself in an item as a to-do. | ToDo |
| [x] | 5. I wait for a review that I requested on my pull request. | My work |
| [ ] | 6. I attach a note to an item. | All tabs |

## 1. My issues and pull requests

I open an issue or a pull request in any repo. The item goes to Mine.

## 2. Action is expected from me

One of these events puts an item in Action:

- Someone mentions me.
- Someone assigns an issue or a pull request to me.
- Someone requests my review on a pull request.

## 3. Watch a repo

I watch specific repos. The app shows the new issues and pull requests in
these repos.

## 4. Mention myself as a to-do

I write `@me` in a comment on an issue or a pull request. The item goes to the
ToDo tab. Example: in a PR, I see that a follow-up PR is necessary. I write a
bullet point with `@me`. I do not open the follow-up PR now.

**Decision:** a new tab, ToDo, after My work. ToDo is for my own tasks. Action
is for the items where other people expect something from me. Detection B.
Done rules A and B. The pop-ups repeat after the reminder interval, as in
Action.

**Before the change:** the app ignored the mention.

- GitHub sends no notification for a self-mention.
- `check_action_items` ignores mentions in my own comments
  (`ghinbox/sync.py:288`).
- My own comment counts as a reply. The reply marks the item done
  (`ghinbox/sync.py:286`).

**Design options: how the app finds a self-mention**

- **A. Search my own comments.** Run the search `commenter:@me updated:>=since`.
  Then scan my comments on each result for `@me`. This finds items that are not
  in Action yet. It costs one comment request for each changed item.
- **B. Use the `mentions:@me` search.** The app runs this search now
  (`sync_mentions`). Cheapest. The test on 2026-10-14 passed: the search found
  `florence-bockting/gh-inbox#3`. In that issue, only I mention myself.
- **C. Remind me in the app, not on GitHub.** I mark the item in the app. I
  write no GitHub comment. Other people do not see the reminder. This is the
  same as option C in scenario 6.

**Design options: when the item is done**

- **A. I mark it done myself.** My later comments do not mark it done.
- **B. A close marks it done.** The app does this now for mentions.
- **C. A later comment from me marks it done.** Not good: the reminder comment
  and a normal reply look the same.

**Display:** give a self-mention its own reason, `todo`. Show the tag
"todo" in a third color, next to the mention tag and the assigned tag. A mention from
another person has a higher priority.

**Open questions:**

- Does the app check only watched repos, or all repos? `_sync_search` now
  drops items from repos that I do not watch.
- Does a self-mention on my own item go to Action, or only stay in Mine?
- Does the pop-up come at once, or after a delay? An example of a delay:
  "@me in 3d".

**Recommended:** detection B. Use done rules A and B together.

**Implemented:** `_add_todo` and `check_todos` in `ghinbox/sync.py`.

## 5. Wait for a requested review

I request a review on my pull request. The reviewer does nothing for N days.
The app tells me. I can then tag the reviewer again.

**Decision:** option A. The pull request is already in My work. A waiting
review is not a task that I set myself, so it does not go to the self-mention
tab.

**Implemented:** `refresh_waiting` in `ghinbox/sync.py`.

- One timer for each reviewer. A team counts as one reviewer, `@org/team`.
- The timer starts at the last review request, or at my last comment that tags
  the reviewer.
- The setting "Review wait (days)" sets N. The default is 3.
- The PR shows the tag "in review" while a review is pending. After N days,
  the tag changes to "review overdue", and the item is highlighted. A pop-up
  comes, and repeats after the reminder interval.
- The app only opens the PR. It does not post a comment.

**Before the change:** the stall flag in My work looked at all activity on the
item, not at the reviewer.

**Data:** `pulls/{n}/requested_reviewers` lists the pending reviewers. The
`review_requested` events in the timeline give the request time. A reviewer
leaves the list after a review.

**Design options:**

- **A. Extend the stall flag in Mine.** The pull request shows
  "waiting for @x, 4d". A pop-up comes after N days. Smallest change.
- **B. New "Waiting" tab.** The tab lists my pull requests with pending
  reviewers. Each row shows the reviewer and the wait time. Clearest view, one
  more tab.
- **C. Move the item to Action when overdue.** After N days the pull request
  goes to Action with the reason `review_overdue`. To tag the reviewer again
  is an action that I must do. A new review request or a review removes it.


## 6. Attach a note to an item

I write a short note on an item, for example "wait for the CI fix".

**Design options:**

- **A. A `note` column in `items`.** Simple. The note stays in one tab. The
  key of `items` is `(key, category)`.
- **B. A `notes` table with the item key.** The note follows the item to all
  tabs, also after a move. Recommended.
- **C. A note with a date.** The note comes back as a reminder on that date.
  This also covers scenario 4 without a GitHub comment.

**Open questions:**

- Where do I edit the note? Options: inline in the web UI, a key in the TUI,
  or both.
- Does the list show the full note, or only an icon?
- Does a done item keep its note?

Notes stay in the local database. The app does not send them to GitHub.
