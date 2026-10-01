from datetime import datetime

from app.date_format import (
    format_day,
    format_day_long,
    format_day_short,
    format_relative,
    format_slot,
    format_time,
    format_time_range,
)

# DESIGN_DIRECTION.md was sampled "on 1 Oct 2026" and its §7 before/after
# table is written against that date — pin "now" to match so format_relative
# and the year-omission rule are deterministic.
NOW = datetime(2026, 10, 1, 12, 0, 0)


def test_table_row_1_day_and_time_range():
    start = datetime(2026, 10, 14, 10, 0)
    end = datetime(2026, 10, 14, 12, 0)
    assert f"{format_day(start)} · {format_time_range(start, end)}" == "Wed 14 Oct · 10:00–12:00"


def test_table_row_2_day_comma_time_range():
    start = datetime(2026, 10, 15, 10, 0)
    end = datetime(2026, 10, 15, 12, 0)
    assert f"{format_day(start)}, {format_time_range(start, end)}" == "Thu 15 Oct, 10:00–12:00"


def test_table_row_3_requested_relative():
    created_at = datetime(2026, 8, 26, 9, 50, 2)
    assert f"Requested {format_relative(created_at, now=NOW)}" == "Requested 26 Aug"


def test_table_row_5_day_comma_time_local():
    # The doc's own example date (7 Oct 2026) is a Wednesday, not the "Fri"
    # shown in the table — an inconsistency in the illustrative example, not
    # a bug here. What matters: no zero-padded day, and the real local time.
    d = datetime(2026, 10, 7, 19, 0)
    assert f"{format_day(d)}, {format_time(d)}" == "Wed 7 Oct, 19:00"


def test_format_day_omits_year_in_current_year(monkeypatch):
    import app.date_format as date_format

    monkeypatch.setattr(date_format, "datetime", _FixedNow)
    assert date_format.format_day(datetime(2026, 10, 14)) == "Wed 14 Oct"


def test_format_day_includes_year_when_not_current(monkeypatch):
    import app.date_format as date_format

    monkeypatch.setattr(date_format, "datetime", _FixedNow)
    assert date_format.format_day(datetime(2027, 10, 14)) == "Thu 14 Oct 2027"


def test_format_day_never_zero_pads():
    assert format_day(datetime(2026, 10, 3)) == "Sat 3 Oct"


def test_format_day_short_has_no_weekday():
    assert format_day_short(datetime(2026, 8, 26)) == "26 Aug"


def test_format_day_long_spells_everything_out():
    assert format_day_long(datetime(2026, 10, 14)) == "Wednesday 14 October 2026"


def test_format_time_is_24_hour_no_seconds():
    assert format_time(datetime(2026, 10, 14, 19, 5)) == "19:05"


def test_format_slot_includes_duration():
    start = datetime(2026, 10, 14, 10, 0)
    end = datetime(2026, 10, 14, 12, 0)
    assert format_slot(start, end) == "Wed 14 Oct · 10:00–12:00 · 2 hours"


def test_format_slot_uses_minutes_under_an_hour():
    start = datetime(2026, 10, 14, 10, 0)
    end = datetime(2026, 10, 14, 10, 45)
    assert format_slot(start, end) == "Wed 14 Oct · 10:00–10:45 · 45 min"


def test_format_relative_today_yesterday_and_days_ago():
    assert format_relative(datetime(2026, 10, 1, 8, 0), now=NOW) == "today"
    assert format_relative(datetime(2026, 9, 30), now=NOW) == "yesterday"
    assert format_relative(datetime(2026, 9, 27), now=NOW) == "4 days ago"


def test_format_relative_falls_back_to_absolute_beyond_a_week():
    assert format_relative(datetime(2026, 9, 20), now=NOW) == "20 Sep"


class _FixedNow(datetime):
    @classmethod
    def utcnow(cls):
        return NOW
