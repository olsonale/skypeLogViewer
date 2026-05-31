from __future__ import annotations

from datetime import datetime

PREVIEW_LIMIT = 256


def to_local(dt: datetime) -> datetime:
    """Convert a (UTC) datetime to the machine's local timezone."""
    return dt.astimezone()


def format_12h(dt: datetime) -> str:
    """Format as 'Mar 19, 2025, 3:14 PM'. Formats dt as-is (no tz conversion)."""
    hour = dt.hour % 12 or 12
    meridiem = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}, {hour}:{dt.minute:02d} {meridiem}"


def format_timestamp(dt: datetime) -> str:
    """Convert to local time, then format as 12-hour."""
    return format_12h(to_local(dt))


def date_label(dt: datetime) -> str:
    """Format the day as 'Wednesday, March 19, 2025' (no tz conversion)."""
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year}"


def make_preview(text: str, limit: int = PREVIEW_LIMIT) -> str:
    """Collapse whitespace and truncate to `limit` chars with an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_row(sender: str, dt: datetime, preview: str) -> str:
    """Build a message-list row label: 'You, Mar 19, 2025, 3:14 PM: hey there'."""
    return f"{sender}, {format_12h(dt)}: {preview}"
