# Time-jump navigation in the message list

Date: 2026-05-31

## Goal

Let the user move through a conversation's message list by larger time
increments than a single row, using the keyboard, with each jump announced
clearly by a screen reader.

## Keys

Active **only when the message list (`msg_list`) has focus**. All jumps target
date-separator rows.

| Key                     | Action                          |
|-------------------------|---------------------------------|
| Shift+Down / Shift+Up   | Next / previous **day**         |
| Ctrl+Down / Ctrl+Up     | Next / previous **calendar month** |
| Page Down / Page Up     | Next / previous **calendar year**  |

## Behavior

- **Landing target is the date-separator row** (`— Monday, May 5, 2025 —`). The
  screen reader announces the full date, so the user hears exactly where they
  landed. Down arrow then steps into that period's messages. (Message rows show
  only sender + time + preview, not the date, which is why separators are the
  target.)

- **"Previous" is smart (start-of-current-period first).** If the current
  selection is partway through a period, the first press moves to the *start* of
  the current period (its leading separator); a second press moves to the
  previous period.
  - Shift+Up from a mid-day message → that day's separator; again → previous
    day's separator.
  - Ctrl+Up → first day-separator of the current month; again → first
    day-separator of the previous month.
  - Page Up → first day-separator of the current year; again → first
    day-separator of the previous year.

- **"Next" always moves forward** to the first day-separator that begins a
  strictly later period than the current selection's period. Gaps in the data
  (months/years with no messages) are skipped — "next month" lands on the first
  day that actually has messages in a later month.

- **At a boundary** (no further period in the requested direction):
  `wx.MessageBeep()` plus a status-bar message ("No earlier day", "No later
  month", etc.), consistent with the existing find-at-end behavior. The
  selection does not move.

- **Filtered view:** navigation operates on the rows currently displayed. The
  separators are rebuilt for the filtered set, so jumps stay within visible
  days.

## Architecture / components

### 1. New pure module `skype_log_viewer/navigation.py`

```
def time_jump_target(meta, current, unit, direction) -> Optional[int]
```

- `meta`: list of `(date, is_separator)` tuples, one per row, in display order.
  `date` is the row's local calendar date (`datetime.date`); `is_separator` is
  `True` for date-separator rows.
- `current`: index of the currently selected row.
- `unit`: `"day"`, `"month"`, or `"year"`.
- `direction`: `+1` (next) or `-1` (previous).
- Returns the target row index (always a separator row) or `None` when there is
  no period in that direction (boundary).

No wx dependency. Pure data in, index out — fully unit-testable.

**Logic outline:**
- `seps` = ordered list of indices where `is_separator` is `True`.
- `key(date)` projects the date to the comparison granularity: `(y, m, d)` for
  day, `(y, m)` for month, `(y,)` for year.
- Every day-block begins with exactly one separator (guaranteed by
  `rebuild_rows`), so there is always a separator at or before `current`; `p` is
  the position in `seps` of the current period's leading separator group.
- **Next:** return the first separator index `> current` whose `key` is greater
  than the current `key` (chronological order guarantees "first different =
  first later").
- **Previous (smart):** walk back to the earliest separator sharing the current
  `key` (the period start). If `current` is past that separator, return it.
  Otherwise (already at the period start), walk to the previous period and
  return the earliest separator of *its* `key`. Return `None` if there is no
  earlier period.

### 2. `_Row` gains a `date` field

Add `date: datetime.date` to `_Row.__slots__`. In `rebuild_rows`, set it for
both the separator row and each message row of a day (the day's local date,
already computed as `day`). This lets the frame build `meta` cheaply and gives
the pure function dates without re-parsing separator label text.

### 3. `main_frame` key handling

- In `on_char_hook`, when `wx.Window.FindFocus() is self.msg_list` and
  `self.rows` is non-empty, map the six combos to `_time_jump(unit, direction)`
  and `return` (consume the event). Disambiguate modifiers: Shift+arrow requires
  ShiftDown and not ControlDown; Ctrl+arrow requires ControlDown and not
  ShiftDown; Page keys map regardless of those modifiers. All other cases
  `event.Skip()`.
- New method `_time_jump(self, unit, direction)`:
  - Build `meta` from `self.rows` (`(row.date, row.message is None)`).
  - `current = self.msg_list.GetFirstSelected()` (fall back to 0 if none).
  - `target = time_jump_target(meta, current, unit, direction)`.
  - If `target is not None`: `self._select_row(target)`.
  - Else: `wx.MessageBeep()` and `self.SetStatusText(...)` with a message keyed
    to unit + direction.

Selecting a separator row is already supported: `_update_detail` shows
`row.text` for separator rows and does not save a position (only message rows
update saved position), which is the desired behavior.

### 4. `shortcuts_dialog.py`

Add three lines to `SHORTCUTS_TEXT`:

```
Shift+Up / Down Jump to previous / next day
Ctrl+Up / Down  Jump to previous / next calendar month
Page Up / Down  Jump to previous / next calendar year
```

## Testing

### `tests/test_navigation.py` (pure unit tests)

Synthetic `meta` covering multiple days across month and year boundaries, with
gaps. Assert:
- Next day / previous day from a mid-day position.
- Smart previous: first press lands on current period start, second press on
  previous period (for day, month, year).
- Next month / next year skip empty months/years (gap-skipping).
- Boundary cases return `None` (next past last period, previous before first).
- `current` on a separator vs. on a message row both behave correctly.

### `tests/test_ui_smoke.py` (frame-level)

- Build a frame, select a conversation with messages spanning at least two days
  (extend the fixture or the in-test conversation as needed), call
  `frame._time_jump("day", +1)` / `(-1)` and assert `GetFirstSelected()` moved
  to the expected separator row.
- Assert the new key labels (`Shift+Up`, `Ctrl+Up`, `Page Up`) appear in
  `SHORTCUTS_TEXT`.

## Out of scope

- Jumping by week.
- Any change to conversation-list navigation.
- A visible "month" or "year" separator row (months/years are reached via the
  first day-separator of that period).
