# Time-Jump Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a keyboard user jump through a conversation's message list by day, calendar month, or calendar year, landing on date-separator rows so a screen reader announces the destination.

**Architecture:** A new pure module `navigation.py` computes a target row index from a list of `(date, is_separator)` tuples — no wx dependency, fully unit-testable. `_Row` gains a `date` field so the frame can build that list cheaply. `MainFrame.on_char_hook` maps six key combos (Shift/Ctrl + Up/Down, Page Up/Down) to a new `_time_jump` method that calls the pure function and either selects the target separator or beeps at a boundary.

**Tech Stack:** Python 3, wxPython (`wx.ListCtrl` virtual list, `wx.EVT_CHAR_HOOK`), pytest, uv for dependency management and test running.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `skype_log_viewer/navigation.py` | Pure index math for time jumps | **Create** |
| `tests/test_navigation.py` | Unit tests for the pure function | **Create** |
| `skype_log_viewer/ui/main_frame.py` | `_Row.date`, `rebuild_rows` plumbing, key handling, `_time_jump` | **Modify** |
| `skype_log_viewer/ui/shortcuts_dialog.py` | Document the three new key combos | **Modify** |
| `tests/test_ui_smoke.py` | Frame-level tests for row dates, `_time_jump`, shortcuts text | **Modify** |

---

## Task 1: Pure navigation module

The core logic: given per-row `(date, is_separator)` tuples, a current row index, a unit, and a direction, return the target separator row index (or `None` at a boundary). "Next" jumps to the first separator in a strictly later period (skipping empty months/years). "Previous" is smart: first to the start of the current period, then to the previous period.

**Files:**
- Create: `skype_log_viewer/navigation.py`
- Test: `tests/test_navigation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_navigation.py`:

```python
from datetime import date

from skype_log_viewer.navigation import time_jump_target


def _meta(spec):
    """Build (date, is_separator) rows from [(date, n_messages), ...].

    Each day-block is one separator row followed by n_messages message rows,
    matching how rebuild_rows lays out the virtual list.
    """
    rows = []
    for day, n in spec:
        rows.append((day, True))
        for _ in range(n):
            rows.append((day, False))
    return rows


# Dataset: two days in Jan 2025 (same month), a gap over Feb to Mar 2025,
# then a year gap to Jul 2026. Separator rows land at indices 0, 3, 5, 8.
META = _meta([
    (date(2025, 1, 5), 2),    # rows 0(sep),1,2
    (date(2025, 1, 20), 1),   # rows 3(sep),4
    (date(2025, 3, 10), 2),   # rows 5(sep),6,7
    (date(2026, 7, 1), 1),    # rows 8(sep),9
])


def test_next_day_from_mid_day():
    # message row inside Jan 5 -> Jan 20 separator
    assert time_jump_target(META, current=1, unit="day", direction=1) == 3
    # message row inside Jan 20 -> Mar 10 separator
    assert time_jump_target(META, current=4, unit="day", direction=1) == 5


def test_previous_day_smart_two_presses():
    # first press: mid Jan 20 -> Jan 20 separator (start of current day)
    assert time_jump_target(META, current=4, unit="day", direction=-1) == 3
    # second press: at Jan 20 separator -> previous day Jan 5 separator
    assert time_jump_target(META, current=3, unit="day", direction=-1) == 0


def test_previous_month_smart_two_presses():
    # first press: mid Mar 10 -> Mar 10 separator (start of current month)
    assert time_jump_target(META, current=6, unit="month", direction=-1) == 5
    # second press: at Mar 10 separator -> earliest separator of previous
    # month-with-data (Feb is empty, so Jan 2025 -> index 0)
    assert time_jump_target(META, current=5, unit="month", direction=-1) == 0


def test_previous_year_smart_two_presses():
    # first press: mid Jul 2026 -> Jul 2026 separator (start of current year)
    assert time_jump_target(META, current=9, unit="year", direction=-1) == 8
    # second press: at Jul 2026 separator -> earliest separator of 2025
    assert time_jump_target(META, current=8, unit="year", direction=-1) == 0


def test_next_month_skips_empty_months():
    # Jan 5 -> Mar 10 (Feb has no data and Jan 20 is the same month, both skipped)
    assert time_jump_target(META, current=1, unit="month", direction=1) == 5
    # Mar 10 -> Jul 2026
    assert time_jump_target(META, current=5, unit="month", direction=1) == 8


def test_next_year_skips_empty_years():
    # Jan 2025 -> Jul 2026 (rest of 2025 skipped)
    assert time_jump_target(META, current=1, unit="year", direction=1) == 8


def test_next_at_last_period_returns_none():
    assert time_jump_target(META, current=8, unit="year", direction=1) is None
    assert time_jump_target(META, current=9, unit="day", direction=1) is None


def test_previous_before_first_period_returns_none():
    assert time_jump_target(META, current=0, unit="day", direction=-1) is None
    assert time_jump_target(META, current=0, unit="month", direction=-1) is None
    assert time_jump_target(META, current=0, unit="year", direction=-1) is None


def test_current_on_separator_and_on_message_both_work():
    # current on a separator row (index 3, Jan 20 sep)
    assert time_jump_target(META, current=3, unit="day", direction=1) == 5
    # current on a message row (index 4, inside Jan 20)
    assert time_jump_target(META, current=4, unit="day", direction=1) == 5


def test_no_separators_returns_none():
    assert time_jump_target([], current=0, unit="day", direction=1) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_navigation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.navigation'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/navigation.py`:

```python
from __future__ import annotations

from typing import Optional


def _projector(unit: str):
    """Return a function projecting a date to the comparison granularity.

    Tuples compare chronologically, so "first different key" == "first later
    period" for rows already in chronological order.
    """
    if unit == "day":
        return lambda d: (d.year, d.month, d.day)
    if unit == "month":
        return lambda d: (d.year, d.month)
    if unit == "year":
        return lambda d: (d.year,)
    raise ValueError(f"unknown unit: {unit!r}")


def time_jump_target(meta, current: int, unit: str, direction: int) -> Optional[int]:
    """Index of the separator row to jump to, or None at a boundary.

    meta: sequence of (date, is_separator) per row, in display order.
    current: index of the currently selected row.
    unit: "day", "month", or "year".
    direction: +1 (next) or -1 (previous, smart start-of-period-first).
    """
    proj = _projector(unit)
    seps = [i for i, (_, is_sep) in enumerate(meta) if is_sep]
    if not seps:
        return None
    cur_key = proj(meta[current][0])

    if direction > 0:
        # First separator in a strictly later period (gaps skip themselves).
        for s in seps:
            if proj(meta[s][0]) > cur_key:
                return s
        return None

    # Previous (smart): the leading separator of the current period comes first.
    period_start = next(s for s in seps if proj(meta[s][0]) == cur_key)
    if current > period_start:
        return period_start
    # Already at the period start: jump to the previous period that has data.
    earlier = [proj(meta[s][0]) for s in seps if proj(meta[s][0]) < cur_key]
    if not earlier:
        return None
    prev_key = max(earlier)
    return next(s for s in seps if proj(meta[s][0]) == prev_key)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_navigation.py -v`
Expected: PASS — all 10 tests green.

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/navigation.py tests/test_navigation.py
git commit -m "feat: add pure time-jump-target navigation module"
```

---

## Task 2: Give each row a date

The pure function needs a `date` per row. Add `date` to `_Row` and populate it in `rebuild_rows` (the day is already computed as `day`).

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py:36-43` (the `_Row` class)
- Modify: `skype_log_viewer/ui/main_frame.py:209-227` (`rebuild_rows`)
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_smoke.py` (top of file already has `import datetime` and `wx = pytest.importorskip("wx")`):

```python
def test_rebuild_rows_assigns_dates(tmp_path):
    from pathlib import Path
    from skype_log_viewer.formatting import to_local
    from skype_log_viewer.loader import load_export
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    app = wx.App()
    fixture = Path(__file__).parent / "fixtures" / "sample_export.json"
    data = load_export(fixture)
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)
    frame.select_conversation(0)  # "Alice" (conversations sort alphabetically)

    rows = frame.rows
    assert rows
    for row in rows:
        assert isinstance(row.date, datetime.date)
    # message rows carry their own local date
    for row in rows:
        if row.message is not None:
            assert row.date == to_local(row.message.timestamp).date()
    # each separator's date matches the row that follows it
    for i, row in enumerate(rows):
        if row.message is None:
            assert rows[i + 1].date == row.date

    frame.Destroy()
    app.Destroy()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_rebuild_rows_assigns_dates -v`
Expected: FAIL — `TypeError: __init__() takes 3 positional arguments but 4 were given` (the test path never runs because `_Row` has no `date`; the assertion `isinstance(row.date, ...)` would raise `AttributeError`. Either failure confirms the field is missing.)

- [ ] **Step 3: Add the `date` field to `_Row`**

In `skype_log_viewer/ui/main_frame.py`, replace the `_Row` class (lines 36-43):

```python
class _Row:
    """A row in the message list: either a date separator or a message."""

    __slots__ = ("text", "message", "date")

    def __init__(self, text: str, message: Optional[Message], date: datetime.date) -> None:
        self.text = text
        self.message = message
        self.date = date
```

- [ ] **Step 4: Import `datetime` for the annotation**

In `skype_log_viewer/ui/main_frame.py`, add an import near the top (after `from typing import Optional` on line 3):

```python
import datetime
```

So the import block reads:

```python
from __future__ import annotations

import datetime
from typing import Optional

import wx
```

- [ ] **Step 5: Populate `date` in `rebuild_rows`**

In `skype_log_viewer/ui/main_frame.py`, update the two `_Row(...)` constructions inside the `for m in messages:` loop (lines 217-224). Replace:

```python
        for m in messages:
            local = to_local(m.timestamp)
            day = local.date()
            if day != last_day:
                rows.append(_Row(f"— {date_label(local)} —", None))
                last_day = day
            preview = make_preview(m.clean_text)
            rows.append(_Row(format_row(m.sender_name, local, preview), m))
```

with:

```python
        for m in messages:
            local = to_local(m.timestamp)
            day = local.date()
            if day != last_day:
                rows.append(_Row(f"— {date_label(local)} —", None, day))
                last_day = day
            preview = make_preview(m.clean_text)
            rows.append(_Row(format_row(m.sender_name, local, preview), m, day))
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_rebuild_rows_assigns_dates -v`
Expected: PASS

- [ ] **Step 7: Run the full suite to confirm no regressions**

Run: `uv run pytest -v`
Expected: PASS — all existing tests still green (the new `date` field is the only `_Row` change).

- [ ] **Step 8: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: add date field to message-list rows"
```

---

## Task 3: Wire up the jump method and keys

Add `_time_jump`, a status-message lookup, and the six key combos in `on_char_hook`.

**Files:**
- Modify: `skype_log_viewer/ui/main_frame.py` (imports, new `_time_jump` method + label map, `on_char_hook`)
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ui_smoke.py`:

```python
def _frame_with_two_days(tmp_path):
    from pathlib import Path
    from skype_log_viewer.loader import load_export
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    fixture = Path(__file__).parent / "fixtures" / "sample_export.json"
    data = load_export(fixture)
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)
    frame.select_conversation(0)  # Alice: two messages ~35h apart => 2+ day blocks
    return frame


def test_time_jump_day_moves_between_separators(tmp_path):
    app = wx.App()
    frame = _frame_with_two_days(tmp_path)
    seps = [i for i, r in enumerate(frame.rows) if r.message is None]
    assert len(seps) >= 2

    frame._select_row(seps[0])
    frame._time_jump("day", 1)
    assert frame.msg_list.GetFirstSelected() == seps[1]

    # smart previous from the second day's separator -> previous day's separator
    frame._time_jump("day", -1)
    assert frame.msg_list.GetFirstSelected() == seps[0]

    frame.Destroy()
    app.Destroy()


def test_time_jump_at_boundary_does_not_move(tmp_path):
    app = wx.App()
    frame = _frame_with_two_days(tmp_path)
    seps = [i for i, r in enumerate(frame.rows) if r.message is None]

    frame._select_row(seps[0])
    frame._time_jump("day", -1)  # already at the first period -> boundary
    assert frame.msg_list.GetFirstSelected() == seps[0]
    assert "earlier day" in frame.GetStatusBar().GetStatusText().lower()

    frame.Destroy()
    app.Destroy()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui_smoke.py::test_time_jump_day_moves_between_separators tests/test_ui_smoke.py::test_time_jump_at_boundary_does_not_move -v`
Expected: FAIL — `AttributeError: 'MainFrame' object has no attribute '_time_jump'`

- [ ] **Step 3: Import the pure function**

In `skype_log_viewer/ui/main_frame.py`, add to the relative imports (after line 8, `from ..model import ...`):

```python
from ..navigation import time_jump_target
```

- [ ] **Step 4: Add the status-message lookup**

In `skype_log_viewer/ui/main_frame.py`, add this module-level constant after the menu id definitions (after `ID_SHORTCUTS = wx.NewIdRef()`, around line 21):

```python
_JUMP_BOUNDARY_MESSAGE = {
    ("day", 1): "No later day",
    ("day", -1): "No earlier day",
    ("month", 1): "No later month",
    ("month", -1): "No earlier month",
    ("year", 1): "No later year",
    ("year", -1): "No earlier year",
}
```

- [ ] **Step 5: Add the `_time_jump` method**

In `skype_log_viewer/ui/main_frame.py`, add this method to `MainFrame` in the `# ---------- key handling ----------` section, right after `_cycle_pane` (after line 382):

```python
    def _time_jump(self, unit: str, direction: int) -> None:
        if not self.rows:
            return
        meta = [(row.date, row.message is None) for row in self.rows]
        current = self.msg_list.GetFirstSelected()
        if current < 0:
            current = 0
        target = time_jump_target(meta, current, unit, direction)
        if target is not None:
            self._select_row(target)
        else:
            wx.MessageBeep()
            self.SetStatusText(_JUMP_BOUNDARY_MESSAGE[(unit, direction)])
```

- [ ] **Step 6: Handle the keys in `on_char_hook`**

In `skype_log_viewer/ui/main_frame.py`, update `on_char_hook` (lines 359-372). Insert the jump block immediately before the final `event.Skip()`. Replace:

```python
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and wx.Window.FindFocus() is self.conv_list:
            self.msg_list.SetFocus()
            return
        event.Skip()
```

with:

```python
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and wx.Window.FindFocus() is self.conv_list:
            self.msg_list.SetFocus()
            return
        if wx.Window.FindFocus() is self.msg_list and self.rows:
            shift = event.ShiftDown()
            ctrl = event.ControlDown()
            if key in (wx.WXK_DOWN, wx.WXK_UP):
                direction = 1 if key == wx.WXK_DOWN else -1
                if shift and not ctrl:
                    self._time_jump("day", direction)
                    return
                if ctrl and not shift:
                    self._time_jump("month", direction)
                    return
            elif key in (wx.WXK_PAGEDOWN, wx.WXK_PAGEUP):
                direction = 1 if key == wx.WXK_PAGEDOWN else -1
                self._time_jump("year", direction)
                return
        event.Skip()
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui_smoke.py::test_time_jump_day_moves_between_separators tests/test_ui_smoke.py::test_time_jump_at_boundary_does_not_move -v`
Expected: PASS

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS — everything green.

- [ ] **Step 9: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: jump message list by day, month, year via keyboard"
```

---

## Task 4: Document the shortcuts

Add the three combos to the shortcuts dialog and assert they appear.

**Files:**
- Modify: `skype_log_viewer/ui/shortcuts_dialog.py:5-20` (`SHORTCUTS_TEXT`)
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_smoke.py`:

```python
def test_shortcuts_text_lists_time_jump_keys():
    from skype_log_viewer.ui.shortcuts_dialog import SHORTCUTS_TEXT
    for key in ("Shift+Up", "Ctrl+Up", "Page Up"):
        assert key in SHORTCUTS_TEXT
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_shortcuts_text_lists_time_jump_keys -v`
Expected: FAIL — `assert 'Shift+Up' in SHORTCUTS_TEXT`

- [ ] **Step 3: Add the three lines**

In `skype_log_viewer/ui/shortcuts_dialog.py`, insert three lines into `SHORTCUTS_TEXT` after the `Home / End` line. Replace:

```python
Up / Down       Move within the focused list
Home / End      Jump to start / end of the list
Enter           From conversations: move focus into the message list
```

with:

```python
Up / Down       Move within the focused list
Home / End      Jump to start / end of the list
Shift+Up / Down Jump to previous / next day (in the message list)
Ctrl+Up / Down  Jump to previous / next calendar month (in the message list)
Page Up / Down  Jump to previous / next calendar year (in the message list)
Enter           From conversations: move focus into the message list
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py::test_shortcuts_text_lists_time_jump_keys -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS — all tests green.

- [ ] **Step 6: Commit**

```bash
git add skype_log_viewer/ui/shortcuts_dialog.py tests/test_ui_smoke.py
git commit -m "docs: list time-jump shortcuts in the keyboard help"
```

---

## Self-Review

**Spec coverage:**
- Keys table (Shift/Ctrl + Up/Down, Page Up/Down) → Task 3 Step 6; documented in Task 4.
- Landing on date-separator rows → `time_jump_target` always returns a separator index (Task 1); `_select_row` selects it (Task 3).
- Smart "previous" (start-of-period first) → Task 1 `test_previous_*_smart_two_presses`.
- "Next" always strictly later, gap-skipping → Task 1 `test_next_*_skips_empty_*`.
- Boundary: beep + status, no move → Task 3 `_time_jump` else branch + `test_time_jump_at_boundary_does_not_move`.
- Filtered view operates on displayed rows → `_time_jump` builds `meta` from `self.rows`, which `rebuild_rows` already filters (no extra work needed).
- Modifier disambiguation (Shift not Ctrl; Ctrl not Shift; Page keys regardless) → Task 3 Step 6.
- Selecting a separator shows its text and saves no position → existing `_update_detail` already does this (spec §Behavior, no change required).
- `_Row.date` field set for separators and messages → Task 2.
- `navigation.py` pure, no wx → Task 1.
- shortcuts_dialog lines → Task 4.
- Tests `test_navigation.py` + frame-level → Tasks 1 and 3.

**Placeholder scan:** No TBDs; every code step shows complete code; every test step shows the assertion.

**Type consistency:** `time_jump_target(meta, current, unit, direction)` signature is identical across the pure module (Task 1), its tests (Task 1), and the caller `_time_jump` (Task 3). `_Row(text, message, date)` constructor matches both call sites in `rebuild_rows` (Task 2). `_JUMP_BOUNDARY_MESSAGE` keys `(unit, direction)` match the `("day"|"month"|"year", 1|-1)` calls.
