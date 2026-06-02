from datetime import UTC, datetime

from app.dates import (
    _ordinal,
    format_date_prefix,
    has_date_prefix,
    parse_iso_utc,
    strip_date_prefix,
)


def test_ordinals():
    assert _ordinal(1) == "st"
    assert _ordinal(2) == "nd"
    assert _ordinal(3) == "rd"
    assert _ordinal(4) == "th"
    assert _ordinal(11) == "th"
    assert _ordinal(12) == "th"
    assert _ordinal(13) == "th"
    assert _ordinal(21) == "st"
    assert _ordinal(22) == "nd"
    assert _ordinal(23) == "rd"
    assert _ordinal(31) == "st"


def test_format_date_prefix_pacific():
    # 2026-05-10 18:00 UTC -> 11:00 PDT, still May 10 (a Sunday)
    dt = datetime(2026, 5, 10, 18, 0, tzinfo=UTC)
    assert format_date_prefix(dt, "America/Los_Angeles") == "Sunday, May 10th, 2026 - "


def test_format_date_prefix_crosses_day_in_pacific():
    # 2025-05-11 01:30 UTC -> 2025-05-10 18:30 PDT (Saturday)
    dt = datetime(2025, 5, 11, 1, 30, tzinfo=UTC)
    assert format_date_prefix(dt, "America/Los_Angeles") == "Saturday, May 10th, 2025 - "


def test_has_and_strip_date_prefix():
    titled = "Sunday, May 10th, 2026 - Worship Service"
    assert has_date_prefix(titled) is True
    assert strip_date_prefix(titled) == "Worship Service"


def test_no_date_prefix():
    assert has_date_prefix("Worship Service") is False
    assert strip_date_prefix("Worship Service") == "Worship Service"


def test_parse_iso_utc():
    dt = parse_iso_utc("2025-05-11T01:30:00Z")
    assert dt == datetime(2025, 5, 11, 1, 30, tzinfo=UTC)


def test_format_date_prefix_fall_back_uses_pdt_not_pst():
    # 2026-11-01 07:30 UTC is 00:30 PDT (daylight time until 02:00 local / 09:00 UTC).
    # Naively assuming PST (UTC-8) would wrongly roll back to Oct 31.
    dt = datetime(2026, 11, 1, 7, 30, tzinfo=UTC)
    assert format_date_prefix(dt, "America/Los_Angeles") == "Sunday, November 1st, 2026 - "


def test_format_date_prefix_spring_forward_morning():
    # 2026-03-08 09:30 UTC is 01:30 PST, just before the 02:00->03:00 spring-forward.
    dt = datetime(2026, 3, 8, 9, 30, tzinfo=UTC)
    assert format_date_prefix(dt, "America/Los_Angeles") == "Sunday, March 8th, 2026 - "


def test_format_date_prefix_naive_datetime_treated_as_utc():
    # A tz-naive datetime must be interpreted as UTC, then converted to Pacific.
    naive = datetime(2026, 5, 11, 1, 30)  # == 2026-05-10 18:30 PDT
    assert format_date_prefix(naive, "America/Los_Angeles") == "Sunday, May 10th, 2026 - "
