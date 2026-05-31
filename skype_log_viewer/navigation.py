from __future__ import annotations

import datetime
from typing import Callable, Optional, Sequence, Tuple

Meta = Sequence[Tuple[datetime.date, bool]]


def _projector(unit: str) -> Callable[[datetime.date], tuple]:
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


def time_jump_target(meta: Meta, current: int, unit: str, direction: int) -> Optional[int]:
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
