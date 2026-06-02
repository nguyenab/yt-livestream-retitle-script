from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.dates import format_date_prefix, has_date_prefix, parse_iso_utc
from app.matching import matches_any


@dataclass(frozen=True)
class Broadcast:
    video_id: str
    title: str
    start_iso: str  # actualStartTime or scheduledStartTime, ISO-8601 UTC


@dataclass(frozen=True)
class Change:
    video_id: str
    old_title: str
    new_title: str


def decide(
    broadcasts: list[Broadcast],
    base_titles: list[str],
    tz: str,
    window_days: int | None = None,
    now_utc: datetime | None = None,
) -> list[Change]:
    """Return retitle changes for broadcasts that match a base title and lack a date.

    If window_days is set, only broadcasts whose start time is within the last
    window_days (relative to now_utc, default current UTC time) are considered.
    """
    changes: list[Change] = []
    ref = now_utc or datetime.now(timezone.utc)
    for b in broadcasts:
        if has_date_prefix(b.title):
            continue
        if not matches_any(b.title, base_titles):
            continue
        start = parse_iso_utc(b.start_iso)
        if window_days is not None and start < ref - timedelta(days=window_days):
            continue
        prefix = format_date_prefix(start, tz)
        changes.append(Change(b.video_id, b.title, prefix + b.title))
    return changes
