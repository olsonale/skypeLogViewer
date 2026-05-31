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
