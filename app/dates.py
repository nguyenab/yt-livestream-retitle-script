from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

# Matches a leading "Weekday, Month Dayth, Year - " prefix.
DATE_PREFIX_RE = re.compile(
    r"^[A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th), \d{4} - "
)


def _ordinal(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def parse_iso_utc(ts: str) -> datetime:
    """Parse a YouTube ISO-8601 timestamp (e.g. '2025-05-11T01:30:00Z') as aware UTC."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def format_date_prefix(dt_utc: datetime, tz: str = "America/Los_Angeles") -> str:
    """Convert a UTC datetime to local tz and return 'Weekday, Month Dayth, Year - '."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    local = dt_utc.astimezone(ZoneInfo(tz))
    return f"{local.strftime('%A, %B')} {local.day}{_ordinal(local.day)}, {local.year} - "


def has_date_prefix(title: str) -> bool:
    return bool(DATE_PREFIX_RE.match(title))


def strip_date_prefix(title: str) -> str:
    return DATE_PREFIX_RE.sub("", title, count=1)
