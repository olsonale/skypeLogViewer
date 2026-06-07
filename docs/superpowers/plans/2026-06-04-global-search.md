# Global Search Across All Conversations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user search every conversation at once via a "Search scope" selector, producing a flat, screen-reader-friendly results list where activating a result jumps to that message in its conversation.

**Architecture:** A new pure helper `grouped_matches` in `search.py` takes `(group_id, items)` pairs plus a query and returns `(group_index, item_index)` pairs — model-agnostic and fully unit-testable. `MainFrame` gains a `wx.RadioBox` scope selector below the search box (added to the F6 pane cycle), a `results_mode` flag (`"normal"`/`"global"`), and a `conv` field on `_Row`. When scope is "All conversations", Enter runs `run_global_search()` which builds result rows prefixed by conversation name; activating a row resets scope and jumps to the message in its conversation. Esc, time-jump, and Ctrl+I are guarded so they behave sensibly in the results view.

**Tech Stack:** Python 3.13, wxPython (`wx.RadioBox`, `wx.ListCtrl` virtual list, `wx.EVT_CHAR_HOOK`), pytest, uv for dependency management and test running.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `skype_log_viewer/search.py` | Add pure `grouped_matches` helper | **Modify** |
| `tests/test_search.py` | Unit tests for `grouped_matches` | **Modify** |
| `skype_log_viewer/ui/main_frame.py` | `_Row.conv`, `_working_messages`, scope RadioBox, `results_mode`, `run_global_search`, activation, Esc/guards, search routing | **Modify** |
| `skype_log_viewer/ui/shortcuts_dialog.py` | Document the scope selector and global search | **Modify** |
| `tests/test_ui_smoke.py` | Frame-level tests for scope box, name flip, global search, activation, Esc, guards, shortcuts text | **Modify** |
| `README.md` | Document the scope selector | **Modify** |
| `CHANGELOG.md` | Add Unreleased entry | **Modify** |

All commands run from the repository root (`V:\projects\skypelogviewer`). Run tests with `uv run pytest`.

---

## Task 1: Pure `grouped_matches` helper

Add a generic, model-agnostic function to `search.py` alongside the existing ones (no `model` import). Given `(group_id, items)` pairs and a query, return `(group_index, item_index)` pairs for every item whose `key(item)` contains `query` case-insensitively. Empty query returns `[]` (consistent with `matching_indices`). Order is groups-in-input-order, then items-in-input-order within each group.

**Files:**
- Modify: `skype_log_viewer/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_search.py`:

```python
from skype_log_viewer.search import grouped_matches


# (group_id, items) pairs — group ids are arbitrary labels, not indices.
GROUPS = [
    ("g0", ["hello world", "goodbye"]),
    ("g1", ["Hello again", "nothing"]),
    ("g2", []),
]


def test_grouped_matches_spans_groups_in_order():
    # "hello" matches item 0 of g0 and item 0 of g1, returned as (group, item) pairs
    assert grouped_matches(GROUPS, "hello") == [(0, 0), (1, 0)]


def test_grouped_matches_case_insensitive():
    assert grouped_matches(GROUPS, "HELLO") == [(0, 0), (1, 0)]


def test_grouped_matches_empty_query_returns_none():
    assert grouped_matches(GROUPS, "") == []


def test_grouped_matches_no_matches_returns_none():
    assert grouped_matches(GROUPS, "zzz") == []


def test_grouped_matches_uses_key_projection():
    groups = [("g0", [{"t": "alpha"}, {"t": "beta"}]),
              ("g1", [{"t": "ALPHA"}])]
    assert grouped_matches(groups, "alpha", key=lambda d: d["t"]) == [(0, 0), (1, 0)]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_search.py -k grouped_matches -v`
Expected: FAIL — `ImportError: cannot import name 'grouped_matches'`.

- [ ] **Step 3: Implement `grouped_matches`**

Append to `skype_log_viewer/search.py`:

```python
def grouped_matches(groups, query: str, key: Key = _identity) -> list[tuple[int, int]]:
    """(group_index, item_index) pairs for items containing query (case-insensitive).

    `groups` is a sequence of (group_id, items) pairs; the group_id is ignored
    for indexing — the returned group index is the position in `groups`. Empty
    query -> [] (consistent with matching_indices). Groups in input order, items
    in input order within each group.
    """
    if not query:
        return []
    q = query.casefold()
    pairs: list[tuple[int, int]] = []
    for gi, (_group_id, items) in enumerate(groups):
        for ii, it in enumerate(items):
            if q in key(it).casefold():
                pairs.append((gi, ii))
    return pairs
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_search.py -v`
Expected: PASS (all grouped_matches tests plus the existing ones).

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/search.py tests/test_search.py
git commit -m "feat: add grouped_matches helper for global search"
```

---

## Task 2: Add `conv` field to `_Row`

`_Row` gains an optional `conv` field (`Optional[Conversation]`), set only on global-result rows so activation knows where to jump. It stays `None` for normal message rows and date separators, so time-jump (which reads `row.message is None`) is unaffected.

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py:48-56`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui_smoke.py`:

```python
def test_normal_rows_have_no_conv(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    assert frame.rows
    for row in frame.rows:
        assert row.conv is None  # conv is only set on global-result rows
    frame.Destroy()
    app.Destroy()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_normal_rows_have_no_conv -v`
Expected: FAIL — `AttributeError: 'main_frame._Row' object has no attribute 'conv'`.

- [ ] **Step 3: Add the field**

In `skype_log_viewer/ui/main_frame.py`, replace the `_Row` class (lines 48-56):

```python
class _Row:
    """A row in the message list: either a date separator or a message."""

    __slots__ = ("text", "message", "date", "conv")

    def __init__(
        self,
        text: str,
        message: Optional[Message],
        date: datetime.date,
        conv: Optional[Conversation] = None,
    ) -> None:
        self.text = text
        self.message = message
        self.date = date
        self.conv = conv  # set only on global-result rows; None otherwise
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_normal_rows_have_no_conv -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: add optional conv field to message rows"
```

---

## Task 3: Extract `_working_messages(conv)` helper

`working_messages()` currently hardcodes `self.current_conv`. Refactor it to delegate to a small `_working_messages(conv)` helper that filters a given conversation's messages by `show_system`, so both the open conversation and the global search use the same rule.

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py:215-220`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui_smoke.py`:

```python
def test_working_messages_helper_respects_show_system(tmp_path):
    from skype_log_viewer.model import ExportData
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    utc = datetime.timezone.utc
    conv = Conversation("8:a", "Alice", False, 2, [
        Message("1", "8:a", "Alice",
                datetime.datetime(2025, 3, 19, 12, 0, tzinfo=utc),
                "RichText", "real message", False),
        Message("2", "8:a", "Alice",
                datetime.datetime(2025, 3, 19, 12, 1, tzinfo=utc),
                "ThreadActivity/AddMember", "", True),
    ])
    data = ExportData("8:me", [conv])

    app = wx.App()
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)
    try:
        frame.config.show_system = False
        assert len(frame._working_messages(conv)) == 1  # system event excluded
        frame.config.show_system = True
        assert len(frame._working_messages(conv)) == 2  # system event included
    finally:
        frame.Destroy()
        app.Destroy()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_working_messages_helper_respects_show_system -v`
Expected: FAIL — `AttributeError: 'MainFrame' object has no attribute '_working_messages'`.

- [ ] **Step 3: Refactor `working_messages`**

In `skype_log_viewer/ui/main_frame.py`, replace `working_messages` (lines 215-220):

```python
    def _working_messages(self, conv: Conversation) -> list[Message]:
        """Messages of `conv` filtered by the Show system events setting."""
        if self.config.show_system:
            return list(conv.messages)
        return [m for m in conv.messages if not m.is_system]

    def working_messages(self) -> list[Message]:
        if not self.current_conv:
            return []
        return self._working_messages(self.current_conv)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_smoke.py -v`
Expected: PASS (the new test plus the existing frame tests still pass).

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "refactor: extract _working_messages(conv) helper"
```

---

## Task 4: Scope RadioBox, `results_mode`, and scope switching

Add the "Search scope" `wx.RadioBox` below the search box, wire it into the F6 pane cycle, initialize `results_mode`, and handle scope changes (flip the search box's accessible name; restore the normal view when leaving the results list). Introduce `_scope_is_global()` and `_restore_normal_view()` here so the scope handler is complete; `run_global_search` (Task 5) will set `results_mode = "global"`.

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py` — `__init__` (line 66 area), `_build_layout` (lines 141-159), `_bind_events` (line 164 area)
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ui_smoke.py`:

```python
def test_scope_radiobox_exists_with_two_options(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    try:
        assert frame.scope_box.GetCount() == 2
        assert frame.scope_box.GetString(0) == "This conversation"
        assert frame.scope_box.GetString(1) == "All conversations"
        # scope box sits in the F6 pane cycle between search and messages
        assert frame._panes.index(frame.scope_box) == \
            frame._panes.index(frame.search_ctrl) + 1
        assert frame._panes.index(frame.scope_box) == \
            frame._panes.index(frame.msg_list) - 1
    finally:
        frame.Destroy()
        app.Destroy()


def test_scope_switch_flips_search_accessible_name(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    try:
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        assert frame.search_ctrl.GetName() == "Search all conversations"
        frame.scope_box.SetSelection(0)
        frame.on_scope_changed(None)
        assert frame.search_ctrl.GetName() == "Search this conversation"
    finally:
        frame.Destroy()
        app.Destroy()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_smoke.py -k "scope" -v`
Expected: FAIL — `AttributeError: 'MainFrame' object has no attribute 'scope_box'`.

- [ ] **Step 3: Initialize `results_mode` in `__init__`**

In `skype_log_viewer/ui/main_frame.py`, find this block in `__init__` (around lines 64-66):

```python
        self.current_conv: Optional[Conversation] = None
        self.rows: list[_Row] = []
        self.search_mode = "filter"  # or "find"
```

Replace it with:

```python
        self.current_conv: Optional[Conversation] = None
        self.rows: list[_Row] = []
        self.search_mode = "filter"  # or "find"
        self.results_mode = "normal"  # or "global" (showing global search results)
```

- [ ] **Step 4: Build the RadioBox in `_build_layout`**

In `_build_layout`, find the search-box block (lines 140-143):

```python
        right.Add(wx.StaticText(panel, label="Search"), 0, wx.ALL, 4)
        self.search_ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName("Search this conversation")
        right.Add(self.search_ctrl, 0, wx.EXPAND | wx.ALL, 4)
```

Insert the RadioBox immediately after it:

```python
        right.Add(wx.StaticText(panel, label="Search"), 0, wx.ALL, 4)
        self.search_ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName("Search this conversation")
        right.Add(self.search_ctrl, 0, wx.EXPAND | wx.ALL, 4)

        self.scope_box = wx.RadioBox(
            panel, label="Search scope",
            choices=["This conversation", "All conversations"],
            style=wx.RA_SPECIFY_ROWS,
        )
        right.Add(self.scope_box, 0, wx.EXPAND | wx.ALL, 4)
```

- [ ] **Step 5: Add the scope box to the F6 pane cycle**

In `_build_layout`, replace the `_panes` assignment (line 159):

```python
        self._panes = [self.conv_list, self.search_ctrl, self.scope_box, self.msg_list, self.detail]
```

- [ ] **Step 6: Bind the scope-change event**

In `_bind_events`, find the search-box bindings (lines 164-165):

```python
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search_text)
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search_enter)
```

Add a scope binding immediately after:

```python
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search_text)
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search_enter)
        self.scope_box.Bind(wx.EVT_RADIOBOX, self.on_scope_changed)
```

- [ ] **Step 7: Add the scope helpers**

In `skype_log_viewer/ui/main_frame.py`, find the start of the search section (line 269-270):

```python
    # ---------- search ----------
    def focus_search(self, mode: str) -> None:
```

Insert these methods just before `focus_search`:

```python
    # ---------- search ----------
    def _scope_is_global(self) -> bool:
        return self.scope_box.GetSelection() == 1

    def on_scope_changed(self, event: wx.CommandEvent) -> None:
        if self._scope_is_global():
            # Don't search yet — global search runs on Enter, not per keystroke.
            self.search_ctrl.SetName("Search all conversations")
            self.search_ctrl.SetFocus()
            self.search_ctrl.SelectAll()
        else:
            self.search_ctrl.SetName("Search this conversation")
            if self.results_mode == "global":
                self._restore_normal_view()

    def _restore_normal_view(self) -> None:
        """Leave the global results list and show the current conversation."""
        self.results_mode = "normal"
        if self.current_conv is not None:
            self.rebuild_rows()
            self._select_row(0)
        else:
            self.rows = []
            self.msg_list.SetItemCount(0)
            self.msg_list.Refresh()
            self.detail.ChangeValue("")

    def focus_search(self, mode: str) -> None:
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_smoke.py -k "scope" -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: add search scope selector and results mode"
```

---

## Task 5: `run_global_search()`

Build `(conv.id, working_messages)` groups from the visible conversations, run `grouped_matches`, and build a flat list of result `_Row`s prefixed by conversation name (`"{conv.display_name} — " + format_row(...)`). Handle the empty-query and no-match cases. Also guard `_update_detail` so it does not persist a scroll position while showing global results.

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py` — import line (line 12), `_update_detail` (lines 262-267), add `run_global_search`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ui_smoke.py`:

```python
def _frame_global(tmp_path):
    """Frame over two conversations that both contain the word 'hello'."""
    from skype_log_viewer.model import ExportData
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    utc = datetime.timezone.utc

    def msg(i, sender, text):
        return Message(str(i), "8:x", sender,
                       datetime.datetime(2025, 3, 19, 12, 0, tzinfo=utc),
                       "RichText", text, False)

    conv_a = Conversation("8:a", "Alice", False, 2,
                          [msg(1, "You", "hello there"), msg(2, "Alice", "banana split")])
    conv_b = Conversation("8:b", "Bob", False, 2,
                          [msg(3, "You", "another hello"), msg(4, "Bob", "nothing here")])
    data = ExportData("8:me", [conv_a, conv_b])
    cfg = Config(tmp_path / "config.json")
    return MainFrame(data, cfg)


def test_run_global_search_builds_prefixed_results(tmp_path):
    app = wx.App()
    frame = _frame_global(tmp_path)
    try:
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        frame.search_ctrl.ChangeValue("hello")
        frame.run_global_search()

        assert frame.results_mode == "global"
        assert frame.msg_list.GetItemCount() == 2
        # one row per match, in conversation order, prefixed by conversation name
        assert frame.rows[0].text.startswith("Alice — ")
        assert frame.rows[1].text.startswith("Bob — ")
        # each result carries its conversation for activation
        assert frame.rows[0].conv.id == "8:a"
        assert frame.rows[1].conv.id == "8:b"
        # the matched messages are the right ones
        assert frame.rows[0].message.id == "1"
        assert frame.rows[1].message.id == "3"
        assert "2 results in 2 conversations" in \
            frame.GetStatusBar().GetStatusText()
    finally:
        frame.Destroy()
        app.Destroy()


def test_run_global_search_empty_query_beeps(tmp_path):
    app = wx.App()
    frame = _frame_global(tmp_path)
    try:
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        frame.search_ctrl.ChangeValue("   ")  # whitespace only
        frame.run_global_search()
        assert frame.results_mode == "normal"  # results not built
        assert frame.msg_list.GetItemCount() == 0
    finally:
        frame.Destroy()
        app.Destroy()


def test_run_global_search_no_matches(tmp_path):
    app = wx.App()
    frame = _frame_global(tmp_path)
    try:
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        frame.search_ctrl.ChangeValue("zzzznope")
        frame.run_global_search()
        assert frame.msg_list.GetItemCount() == 0
        assert 'No matches for "zzzznope"' in \
            frame.GetStatusBar().GetStatusText()
    finally:
        frame.Destroy()
        app.Destroy()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_smoke.py -k "run_global_search" -v`
Expected: FAIL — `AttributeError: 'MainFrame' object has no attribute 'run_global_search'`.

- [ ] **Step 3: Import `grouped_matches`**

In `skype_log_viewer/ui/main_frame.py`, replace the search import (line 12):

```python
from ..search import filter_indices, grouped_matches, matching_indices, next_index
```

- [ ] **Step 4: Guard `_update_detail` against persisting position in global mode**

Replace `_update_detail` (lines 262-267):

```python
    def _update_detail(self, row_index: int) -> None:
        if 0 <= row_index < len(self.rows):
            row = self.rows[row_index]
            self.detail.ChangeValue(row.message.clean_text if row.message else row.text)
            if (self.results_mode == "normal" and self.current_conv
                    and row.message is not None):
                self.config.set_position(self.current_conv.id, row_index)
```

- [ ] **Step 5: Add `run_global_search`**

In `skype_log_viewer/ui/main_frame.py`, find `on_search_enter` (ends at line 299) and insert `run_global_search` immediately after it (before the `# ---------- menu handlers ----------` comment on line 301):

```python
    def run_global_search(self) -> None:
        query = self.search_ctrl.GetValue().strip()
        if not query:
            wx.Bell()
            self.SetStatusText("Type a search term, then press Enter")
            return

        convs = self.visible_conversations()
        groups = [(c.id, self._working_messages(c)) for c in convs]
        pairs = grouped_matches(groups, query, key=lambda m: m.clean_text)

        if not pairs:
            self.results_mode = "global"
            self.rows = []
            self.msg_list.SetItemCount(0)
            self.msg_list.Refresh()
            self.detail.ChangeValue("")
            self.SetStatusText(f'No matches for "{query}"')
            return

        rows: list[_Row] = []
        for gi, ii in pairs:
            conv = convs[gi]
            message = groups[gi][1][ii]
            local = to_local(message.timestamp)
            preview = make_preview(message.clean_text)
            text = f"{conv.display_name} — " + format_row(message.sender_name, local, preview)
            rows.append(_Row(text, message, local.date(), conv=conv))

        self.rows = rows
        self.results_mode = "global"
        self.msg_list.SetItemCount(len(rows))
        self.msg_list.Refresh()
        self.msg_list.SetFocus()
        self._select_row(0)
        conv_count = len({r.conv.id for r in rows})
        self.SetStatusText(f"{len(rows)} results in {conv_count} conversations")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_smoke.py -k "run_global_search" -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: implement run_global_search"
```

---

## Task 6: Route search input by scope

`on_search_enter` runs the global search when scope is "All conversations"; otherwise it keeps the existing per-conversation Find path. `on_search_text` (live typing) only acts when scope is "This conversation" — global scope ignores live typing.

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py` — `on_search_text` (lines 275-278), `on_search_enter` (lines 280-283)
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui_smoke.py`:

```python
def test_live_typing_ignored_in_global_scope(tmp_path):
    app = wx.App()
    frame = _frame_global(tmp_path)
    try:
        frame.select_conversation(0)            # Alice, normal view
        normal_count = frame.msg_list.GetItemCount()
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        frame.search_ctrl.ChangeValue("hello")
        frame.on_search_text(None)              # live typing
        # global scope ignores live typing: list unchanged, still normal mode
        assert frame.results_mode == "normal"
        assert frame.msg_list.GetItemCount() == normal_count

        frame.on_search_enter(None)             # Enter runs the global search
        assert frame.results_mode == "global"
        assert frame.msg_list.GetItemCount() == 2
    finally:
        frame.Destroy()
        app.Destroy()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_live_typing_ignored_in_global_scope -v`
Expected: FAIL — live typing still rebuilds rows / Enter does not branch to global search, so one of the assertions fails.

- [ ] **Step 3: Branch `on_search_text` on scope**

Replace `on_search_text` (lines 275-278):

```python
    def on_search_text(self, event: wx.CommandEvent) -> None:
        if self._scope_is_global():
            return  # global search runs on Enter, not per keystroke
        if self.search_mode == "filter":
            self.rebuild_rows(self.search_ctrl.GetValue())
            self._select_row(0)
```

- [ ] **Step 4: Branch `on_search_enter` on scope**

Replace the start of `on_search_enter` (lines 280-283):

```python
    def on_search_enter(self, event: wx.CommandEvent) -> None:
        if self._scope_is_global():
            self.run_global_search()
            return
        if self.search_mode != "find":
            return
        query = self.search_ctrl.GetValue()
```

(The rest of `on_search_enter` — from `msg_rows = ...` onward — is unchanged.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_live_typing_ignored_in_global_scope -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: route search input by scope"
```

---

## Task 7: Activate a global result to jump to its message

Bind `wx.EVT_LIST_ITEM_ACTIVATED` (currently unbound). When `results_mode == "global"` and the row carries a `conv`, reset scope to "This conversation", select that conversation (rebuilding its normal view), then select the target message row by matching message `id`.

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py` — `_bind_events` (line 163 area), add `on_message_activated` / `_activate_result_row`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui_smoke.py`:

```python
def test_activate_global_result_jumps_to_message(tmp_path):
    app = wx.App()
    frame = _frame_global(tmp_path)
    try:
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        frame.search_ctrl.ChangeValue("hello")
        frame.run_global_search()

        frame._activate_result_row(1)  # the "Bob" result (message id "3")

        assert frame.results_mode == "normal"
        assert frame.scope_box.GetSelection() == 0
        assert frame.search_ctrl.GetName() == "Search this conversation"
        assert frame.current_conv.id == "8:b"
        selected = frame.msg_list.GetFirstSelected()
        assert frame.rows[selected].message.id == "3"
    finally:
        frame.Destroy()
        app.Destroy()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_activate_global_result_jumps_to_message -v`
Expected: FAIL — `AttributeError: 'MainFrame' object has no attribute '_activate_result_row'`.

- [ ] **Step 3: Bind the activation event**

In `_bind_events`, find the message-list bindings (lines 162-163):

```python
        self.Bind(wx.EVT_LISTBOX, self.on_conversation_selected, self.conv_list)
        self.msg_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_message_selected)
```

Add an activation binding immediately after:

```python
        self.Bind(wx.EVT_LISTBOX, self.on_conversation_selected, self.conv_list)
        self.msg_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_message_selected)
        self.msg_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_message_activated)
```

- [ ] **Step 4: Add the activation handlers**

In `skype_log_viewer/ui/main_frame.py`, find `on_message_selected` (lines 259-260):

```python
    def on_message_selected(self, event: wx.ListEvent) -> None:
        self._update_detail(event.GetIndex())
```

Insert the activation handlers immediately after it:

```python
    def on_message_activated(self, event: wx.ListEvent) -> None:
        self._activate_result_row(event.GetIndex())

    def _activate_result_row(self, index: int) -> None:
        """Jump from a global-result row to that message in its conversation."""
        if self.results_mode != "global":
            return
        if not (0 <= index < len(self.rows)):
            return
        row = self.rows[index]
        if row.conv is None or row.message is None:
            return
        target_id = row.message.id
        conv_index = next(
            (i for i, c in enumerate(self._visible_convs) if c.id == row.conv.id),
            None,
        )
        if conv_index is None:
            return
        # Reset scope to This conversation, then land on the message.
        self.scope_box.SetSelection(0)
        self.search_ctrl.SetName("Search this conversation")
        self.results_mode = "normal"
        self.select_conversation(conv_index)  # rebuilds the conversation's normal view
        for i, r in enumerate(self.rows):
            if r.message and r.message.id == target_id:
                self.msg_list.SetFocus()
                self._select_row(i)
                return
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_activate_global_result_jumps_to_message -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: activate a global result to jump to its message"
```

---

## Task 8: Esc to leave results; guard time-jump and Ctrl+I

In the global results view: Esc clears the results, resets scope to "This conversation", and restores the current conversation's normal view. Time-jump shortcuts are inert (no date separators to target), and Ctrl+I (conversation info) is disabled (no single active conversation).

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py` — `on_info` (lines 322-326), `on_char_hook` Esc clause (lines 377-381), `_time_jump` (lines 412-413)
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ui_smoke.py`:

```python
def test_escape_in_global_mode_restores_normal_view(tmp_path):
    app = wx.App()
    frame = _frame_global(tmp_path)
    try:
        frame.select_conversation(0)            # Alice, normal view
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        frame.search_ctrl.ChangeValue("hello")
        frame.run_global_search()
        assert frame.results_mode == "global"

        frame.on_char_hook(_key_event(wx.WXK_ESCAPE))

        assert frame.results_mode == "normal"
        assert frame.scope_box.GetSelection() == 0
        assert frame.search_ctrl.GetName() == "Search this conversation"
        assert frame.current_conv.id == "8:a"     # back in Alice's conversation
    finally:
        frame.Destroy()
        app.Destroy()


def test_time_jump_inert_in_global_mode(tmp_path):
    app = wx.App()
    frame = _frame_global(tmp_path)
    try:
        frame.scope_box.SetSelection(1)
        frame.on_scope_changed(None)
        frame.search_ctrl.ChangeValue("hello")
        frame.run_global_search()
        before = frame.msg_list.GetFirstSelected()
        frame._time_jump("day", 1)
        assert frame.msg_list.GetFirstSelected() == before  # unchanged
    finally:
        frame.Destroy()
        app.Destroy()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_smoke.py -k "global_mode" -v`
Expected: FAIL — Esc takes the existing clear-search path (not the global restore) and `_time_jump` still moves the selection.

- [ ] **Step 3: Guard Ctrl+I in `on_info`**

Replace `on_info` (lines 322-326):

```python
    def on_info(self, event: wx.CommandEvent) -> None:
        if self.results_mode == "global":
            wx.Bell()  # no single active conversation in the results view
            return
        if self.current_conv:
            dlg = InfoDialog(self, self.current_conv)
            dlg.ShowModal()
            dlg.Destroy()
```

- [ ] **Step 4: Add the global Esc clause in `on_char_hook`**

In `on_char_hook`, find the F6 and Esc clauses (lines 374-381):

```python
        if key == wx.WXK_F6:
            self._cycle_pane(forward=not event.ShiftDown())
            return
        if key == wx.WXK_ESCAPE and self.search_ctrl.GetValue():
            self.search_ctrl.ChangeValue("")
            self.rebuild_rows("")
            self._select_row(0)
            return
```

Insert a global-mode Esc clause between the F6 clause and the existing Esc clause:

```python
        if key == wx.WXK_F6:
            self._cycle_pane(forward=not event.ShiftDown())
            return
        if key == wx.WXK_ESCAPE and self.results_mode == "global":
            self.scope_box.SetSelection(0)
            self.search_ctrl.SetName("Search this conversation")
            self.search_ctrl.ChangeValue("")
            self._restore_normal_view()
            return
        if key == wx.WXK_ESCAPE and self.search_ctrl.GetValue():
            self.search_ctrl.ChangeValue("")
            self.rebuild_rows("")
            self._select_row(0)
            return
```

- [ ] **Step 5: Guard `_time_jump`**

Replace the start of `_time_jump` (lines 412-414):

```python
    def _time_jump(self, unit: str, direction: int) -> None:
        if self.results_mode == "global":
            return  # global results have no date separators to target
        if not self.rows:
            return
```

(The rest of `_time_jump` is unchanged.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_smoke.py -k "global_mode" -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite to confirm nothing regressed**

Run: `uv run pytest`
Expected: PASS (all tests).

- [ ] **Step 8: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: guard Esc, time-jump, and Ctrl+I in global results view"
```

---

## Task 9: Documentation (shortcuts, README, CHANGELOG)

Document the scope selector and global search in the in-app shortcuts help, the README, and the CHANGELOG. The shortcuts text gains a line that the smoke test asserts on.

**Files:**
- Modify: `skype_log_viewer/ui/shortcuts_dialog.py:5-23`
- Modify: `README.md:30-36`
- Modify: `CHANGELOG.md:3`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui_smoke.py`:

```python
def test_shortcuts_text_mentions_global_search():
    from skype_log_viewer.ui.shortcuts_dialog import SHORTCUTS_TEXT
    assert "Search scope" in SHORTCUTS_TEXT
    assert "All conversations" in SHORTCUTS_TEXT
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_shortcuts_text_mentions_global_search -v`
Expected: FAIL — the strings are not yet in `SHORTCUTS_TEXT`.

- [ ] **Step 3: Update `SHORTCUTS_TEXT`**

In `skype_log_viewer/ui/shortcuts_dialog.py`, replace the `SHORTCUTS_TEXT` block (lines 5-23):

```python
SHORTCUTS_TEXT = """Keyboard shortcuts

F6 / Shift+F6   Move between panes (conversations, search, scope, messages, detail)
Tab / Shift+Tab Move between controls and menus
Up / Down       Move within the focused list
Home / End      Jump to start / end of the list
Shift+Up / Down Jump to previous / next day (in the message list)
Ctrl+Up / Down  Jump to previous / next calendar month (in the message list)
Page Up / Down  Jump to previous / next calendar year (in the message list)
Enter           From conversations: move focus into the message list
Ctrl+F          Find within the conversation (Enter = next, Shift+Enter = previous)
Ctrl+L          Filter the message list to matches (Esc clears)
Search scope    Choose This conversation or All conversations (below the search box)
                With All conversations, press Enter to search every conversation;
                Enter on a result jumps to that message; Esc returns to normal.
Esc             Clear the current search or leave the global results list
Ctrl+C          Copy the selected message's full text
Ctrl+I          Show conversation info
Ctrl+E          Show or hide system events (joins, leaves, topic changes)
Ctrl+O          Open a different export file
F1              Show this list of shortcuts
"""
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_shortcuts_text_mentions_global_search -v`
Expected: PASS.

- [ ] **Step 5: Update the README**

In `README.md`, replace the keyboard shortcuts bullet list (lines 30-36):

```markdown
- **F6 / Shift+F6** — move between the five panes
- **Ctrl+F** — find within the conversation (Enter = next, Shift+Enter = previous)
- **Ctrl+L** — filter the message list to matches (Esc clears)
- **Search scope** — switch between *This conversation* and *All conversations*
  (the selector below the search box). With *All conversations*, press Enter to
  search every conversation at once; Enter on a result jumps to that message.
- **Ctrl+C** — copy the selected message's full text
- **Ctrl+I** — conversation info
- **Ctrl+E** — show/hide system events
- **Ctrl+O** — open a different export
```

- [ ] **Step 6: Update the CHANGELOG**

In `CHANGELOG.md`, find the `## Unreleased` heading (line 3) and the `### Fixed` section that follows. Insert an `### Added` section between the `## Unreleased` heading and the existing `### Fixed` heading:

```markdown
## Unreleased

### Added
- **Search across every conversation at once.** A *Search scope* selector below
  the search box switches between *This conversation* (the existing behavior) and
  *All conversations*. In *All conversations*, type a term and press **Enter** to
  get a flat list of every matching message, each labeled with its conversation
  so your screen reader announces where the match is before what it says.
  Pressing **Enter** on a result jumps to that message in its conversation, and
  **Esc** returns to your conversation. The scope selector joins the F6 pane
  cycle, and the search box announces the active scope when you land on it.

### Fixed
```

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest`
Expected: PASS (all tests).

- [ ] **Step 8: Commit**

```bash
git add skype_log_viewer/ui/shortcuts_dialog.py README.md CHANGELOG.md tests/test_ui_smoke.py
git commit -m "docs: document the global search scope selector"
```

---

## Final verification

- [ ] **Run the entire test suite one last time**

Run: `uv run pytest`
Expected: PASS — all unit and frame-level tests green.

- [ ] **Manual smoke (optional, requires a real export)**

Run: `uv run python -m skype_log_viewer`
Check with a screen reader: Tab from the search box reaches the *Search scope*
radio; selecting *All conversations* renames the search box and focuses it;
typing a term + Enter produces a conversation-prefixed results list; Enter on a
result lands on that message in its conversation; Esc returns to normal.
