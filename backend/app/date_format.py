"""
Single source of truth for every date/time string rendered into an email or
error message a person reads — see DESIGN_DIRECTION.md §7. No other module
should call strftime() directly on a user-facing string.

Mirrors frontend/src/lib/formatDate.js. strftime's "no leading zero" day
flag (%-d on Linux/macOS, %#d on Windows) isn't portable across the dev
machine (Windows) and Render (Linux), so the day number is built by hand
instead of relying on either.
"""
from datetime import datetime


def _day_no_pad(d: datetime) -> str:
    return str(d.day)


def _with_year_suffix(d: datetime) -> str:
    return "" if d.year == datetime.utcnow().year else f" {d.year}"


def format_day(d: datetime) -> str:
    """'Wed 14 Oct' — adds the year only when it isn't the current year."""
    return f"{d.strftime('%a')} {_day_no_pad(d)} {d.strftime('%b')}{_with_year_suffix(d)}"


def format_day_short(d: datetime) -> str:
    """'26 Aug' — same as format_day but without the weekday."""
    return f"{_day_no_pad(d)} {d.strftime('%b')}{_with_year_suffix(d)}"


def format_day_long(d: datetime) -> str:
    """'Wednesday 14 October 2026' — full form, for email body text."""
    return f"{d.strftime('%A')} {_day_no_pad(d)} {d.strftime('%B')} {d.year}"


def format_time(d: datetime) -> str:
    """'10:00' — 24-hour, no seconds."""
    return d.strftime("%H:%M")


def format_time_range(a: datetime, b: datetime) -> str:
    """'10:00–12:00' — en dash, no spaces."""
    return f"{format_time(a)}–{format_time(b)}"


def _format_duration(a: datetime, b: datetime) -> str:
    minutes = (b - a).total_seconds() / 60
    if minutes < 60:
        return f"{int(minutes)} min"
    hours = round(minutes / 60, 1)
    if hours == int(hours):
        hours = int(hours)
    return f"{hours} hour" + ("" if hours == 1 else "s")


def format_slot(a: datetime, b: datetime) -> str:
    """'Wed 14 Oct · 10:00–12:00 · 2 hours'"""
    return f"{format_day(a)} · {format_time_range(a, b)} · {_format_duration(a, b)}"


def format_relative(d: datetime, now: datetime | None = None) -> str:
    """
    'today' / 'yesterday' / '3 days ago', falling back to an absolute short
    date ('26 Aug') beyond a week — an unreadable '47 days ago' is worse
    than just saying the date.
    """
    now = now or datetime.utcnow()
    days = (now.date() - d.date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    return format_day_short(d)
