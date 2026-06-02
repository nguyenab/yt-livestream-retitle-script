from datetime import datetime, timezone

from app.dates import (
    format_date_prefix,
    has_date_prefix,
    strip_date_prefix,
    parse_iso_utc,
    _ordinal,
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
    dt = datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc)
    assert format_date_prefix(dt, "America/Los_Angeles") == "Sunday, May 10th, 2026 - "


def test_format_date_prefix_crosses_day_in_pacific():
    # 2025-05-11 01:30 UTC -> 2025-05-10 18:30 PDT (Saturday)
    dt = datetime(2025, 5, 11, 1, 30, tzinfo=timezone.utc)
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
    assert dt == datetime(2025, 5, 11, 1, 30, tzinfo=timezone.utc)
