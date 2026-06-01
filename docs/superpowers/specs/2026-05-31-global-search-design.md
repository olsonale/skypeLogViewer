# Global search across all conversations

Date: 2026-05-31

## Goal

Let the user search every conversation at once, not just the open one. A scope
selector beside the search box switches between "This conversation" (today's
behavior) and "All conversations". A global search produces a flat, screen-reader
friendly results list; activating a result jumps to that message in its
conversation.

## Scope selector

A `wx.RadioBox` labeled **"Search scope"** with two options:

| Option              | Meaning                                              |
|---------------------|------------------------------------------------------|
| This conversation   | Default. Search the open conversation (unchanged).   |
| All conversations   | Search every conversation's messages at once.        |

- Placed in the right-hand column directly **below the search box**, so Tab from
  the search field reaches it.
- Added to the **F6 pane cycle**, which becomes:
  Conversations → Search → Search scope → Messages → Detail.
- The search box's accessible name tracks the scope:
  **"Search this conversation"** ↔ **"Search all conversations"**, so the screen
  reader announces the active scope on landing.

## Behavior

### This conversation (default)

Unchanged. Live Filter (Ctrl+L) and match-to-match Find (Ctrl+F / Enter), both
scoped to the open conversation, both matching message text.

### Switching to All conversations

Focus moves to the search box with its text selected, ready to type. The message
list does **not** change yet — the global search runs on Enter, not per
keystroke (a live search over tens of thousands of messages would lag and would
make the screen reader announce a churning list).

### Running a global search (Enter)

- Match is **case-insensitive substring against message text only**
  (`clean_text`), consistent with today's filter. Sender names are not matched.
- The **Show system events** setting is respected: system messages are included
  only when that setting is on, exactly as for the per-conversation working set.
- Builds a **flat results list** — one row per matching message, ordered by
  conversation (in conversation-list order) then chronologically within each
  conversation. **No date-separator rows.**
- Each result row is prefixed with its conversation name, conversation first so
  the screen reader announces *where* before *what*:

  ```
  Family Chat — Alice: see you then, Mar 19, 2025, 3:14 PM
  ```

  i.e. `"{conversation} — " + format_row(sender, local_time, preview)`.
- Focus jumps to the first result. Status bar reports `N results in M
  conversations`.
- **Empty query:** `wx.MessageBeep()` + status prompt; results list not built.
- **No matches:** empty list + `No matches for "{query}"` status.

### Inside the global results list

- **Arrowing** a result updates the Detail pane with that message's full text;
  **Ctrl+C** copies it — same as normal rows.
- **Enter / activate** on a result row:
  1. Resets scope to **This conversation** (radio + search box name).
  2. Selects that result's conversation and rebuilds its normal view.
  3. Selects the target message, leaving the user where the message lives with
     arrow and time-jump navigation back to normal.
- **Esc:** clears the results, resets scope to This conversation, and restores
  the current conversation's normal view.
- **Time-jump shortcuts** (Shift/Ctrl/Page + Up/Down) are inert — there are no
  date separators to target.
- **Ctrl+I** (conversation info) is disabled — there is no single active
  conversation in this view.

## Architecture / components

### 1. `search.py` — new pure helper

Add a generic, model-agnostic function alongside the existing ones (no `model`
import, matching the current file):

```
def grouped_matches(groups, query, key=_identity) -> list[tuple[int, int]]
```

- `groups`: sequence of `(group_id, items)` pairs.
- Returns `(group_index, item_index)` pairs for every item whose `key(item)`
  contains `query` (case-insensitive). Empty query → `[]` (consistent with
  `matching_indices`).
- Order: groups in input order, items in input order within each group.

Pure data in, index pairs out — fully unit-testable.

### 2. `main_frame` — results mode

- **`results_mode` flag** on `MainFrame`: `"normal"` (default) or `"global"`.
  Drives how Enter, Esc, and time-jump behave and how rows are built.
- **`_Row` gains an optional `conv` field** (`Optional[Conversation]`), set only
  on global-result rows so activation knows where to jump. `None` for normal
  message rows and date separators. (Time-jump reads `row.message is None`; the
  new field does not affect it.)

### 3. `main_frame` — UI wiring

- Build the `wx.RadioBox` in `_build_layout`, insert it into `self._panes`
  between `search_ctrl` and `msg_list`.
- Bind `wx.EVT_RADIOBOX` to an `on_scope_changed` handler:
  - → All conversations: set search box name to "Search all conversations",
    focus + select-all the search box. Leave the list as-is until Enter.
  - → This conversation: set name back, restore normal view if currently showing
    global results.
- `on_search_enter` branches on scope:
  - This conversation → existing Find path (only when `search_mode == "find"`).
  - All conversations → `run_global_search()`.
- `on_search_text` (live) only acts when scope is This conversation **and**
  `search_mode == "filter"` — global scope ignores live typing.

### 4. `main_frame` — `run_global_search()`

- Query = trimmed search-box value; empty → beep + status, return.
- Build `groups` from `visible_conversations()`. `working_messages()` currently
  hardcodes `self.current_conv`; refactor it to delegate to a small
  `_working_messages(conv)` helper (filtering `conv.messages` by `show_system`)
  so both the open conversation and the global search use the same rule.
- `pairs = grouped_matches(groups, query, key=lambda m: m.clean_text)`.
- No matches → empty list + status, return.
- Build result `_Row`s: for each pair, `conv` = the conversation, `message` =
  the matched message, `text` = `"{conv.display_name} — " +
  format_row(sender, to_local(ts), make_preview(clean_text))`, `date` =
  local date (unused for navigation but kept for `_Row` shape).
- Set `results_mode = "global"`, populate the virtual list, select row 0, set
  status `N results in M conversations` (M = conversations with ≥1 match).

### 5. `main_frame` — activation, Esc, guards

- **List activate** (`wx.EVT_LIST_ITEM_ACTIVATED`, currently unbound): if
  `results_mode == "global"` and the row has a `conv`, set scope radio to This
  conversation, call the scope reset, `select_conversation(index of conv)`, then
  select the target message row (match by message `id` after the normal rebuild).
- **Esc** (`on_char_hook`): when `results_mode == "global"`, clear results and
  return to normal view for the current conversation instead of the existing
  clear-filter path.
- **Time-jump** and **Ctrl+I**: early-return / disabled when
  `results_mode == "global"`.

### 6. `shortcuts_dialog.py` / `README.md` / `CHANGELOG.md`

- Document the scope selector and all-conversations search (search runs on
  Enter; Enter on a result jumps to it).
- Add a CHANGELOG entry.

## Testing

### `tests/test_search.py` (pure unit tests)

`grouped_matches` over synthetic groups:
- Matches span multiple groups; returned in (group, item) order.
- Case-insensitive.
- Empty query → `[]`.
- No matches → `[]`.
- `key` projection used for matching.

### `tests/test_ui_smoke.py` (frame-level)

- The scope `wx.RadioBox` exists with the two expected labels.
- Switching scope to All conversations flips the search box's accessible name to
  "Search all conversations" (and back).
- `run_global_search` over a fixture with matches in ≥2 conversations populates
  the list with one row per match, rows prefixed by conversation name, and sets
  `results_mode = "global"`.
- Activating a global result row selects the right conversation, selects the
  target message, and resets `results_mode` to `"normal"` and scope to This
  conversation.
- New scope/search wording appears in `SHORTCUTS_TEXT`.

## Out of scope

- Matching sender names, conversation names, dates, or system-event metadata in
  global search (message text only).
- Match-to-match Find (Ctrl+F cycling) across conversations — global scope is
  filter-style only.
- Live (per-keystroke) global search.
- Grouping/expandable tree of results or a separate results window — results
  reuse the existing single message list.
- Persisting the scope selection between sessions or remembering a position in
  the global results list.
