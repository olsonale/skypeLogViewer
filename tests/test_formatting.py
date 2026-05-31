from datetime import datetime, timezone

from skype_log_viewer.formatting import (
    format_12h,
    date_label,
    make_preview,
    format_row,
    PREVIEW_LIMIT,
)


def test_format_12h_afternoon():
    dt = datetime(2025, 3, 19, 15, 14)
    assert format_12h(dt) == "Mar 19, 2025, 3:14 PM"


def test_format_12h_midnight_is_twelve():
    dt = datetime(2025, 3, 19, 0, 5)
    assert format_12h(dt) == "Mar 19, 2025, 12:05 AM"


def test_format_12h_noon_is_twelve_pm():
    dt = datetime(2025, 3, 19, 12, 0)
    assert format_12h(dt) == "Mar 19, 2025, 12:00 PM"


def test_date_label():
    dt = datetime(2025, 3, 19, 12, 0)
    assert date_label(dt) == "Wednesday, March 19, 2025"


def test_make_preview_collapses_whitespace():
    assert make_preview("hello\n\n  world\t!") == "hello world !"


def test_make_preview_truncates_with_ellipsis():
    text = "x" * (PREVIEW_LIMIT + 50)
    out = make_preview(text)
    assert len(out) == PREVIEW_LIMIT
    assert out.endswith("…")


def test_format_row():
    dt = datetime(2025, 3, 19, 15, 14)
    assert format_row("You", dt, "hey there") == "You, Mar 19, 2025, 3:14 PM: hey there"
