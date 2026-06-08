from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
    replaced: bool = False  # True when the original title was overwritten, not just dated


def decide(
    broadcasts: list[Broadcast],
    base_titles: list[str],
    tz: str,
    window_days: int | None = None,
    now_utc: datetime | None = None,
    canonical: str | None = None,
) -> list[Change]:
    """Return retitle changes for dateless livestreams.

    A title already on the ``base_titles`` allowlist is preserved — only the date
    prefix is prepended. If ``canonical`` is given, any other dateless livestream
    (e.g. one a team member overwrote with a sermon title) is rewritten to
    ``<date> - <canonical>``; without ``canonical`` such streams are left alone.

    If window_days is set, only broadcasts whose start time is within the last
    window_days (relative to now_utc, default current UTC time) are considered.
    """
    changes: list[Change] = []
    ref = now_utc or datetime.now(UTC)
    for b in broadcasts:
        if has_date_prefix(b.title):
            continue
        matched = matches_any(b.title, base_titles)
        if not matched and canonical is None:
            continue
        start = parse_iso_utc(b.start_iso)
        if window_days is not None and start < ref - timedelta(days=window_days):
            continue
        prefix = format_date_prefix(start, tz)
        if matched:
            changes.append(Change(b.video_id, b.title, prefix + b.title, replaced=False))
        else:
            changes.append(Change(b.video_id, b.title, prefix + canonical, replaced=True))
    return changes
