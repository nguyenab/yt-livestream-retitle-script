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
    duration_seconds: int | None = None  # video length; None when unknown


@dataclass(frozen=True)
class Change:
    video_id: str
    old_title: str
    new_title: str


@dataclass(frozen=True)
class ReviewRow:
    video_id: str
    date_label: str  # the stream's own Pacific date, e.g. "Sunday, May 10th, 2026"
    title: str  # current (unchanged) title
    start_iso: str
    duration_seconds: int | None = None


def find_unmatched(broadcasts: list[Broadcast], base_titles: list[str], tz: str) -> list[ReviewRow]:
    """Read-only: the livestreams worth a human look — neither already dated nor on the
    allowlist. Sorted oldest-first. The date label carries the weekday so non-Sunday
    streams (which are not worship services) stand out at a glance. No changes implied.
    """
    rows: list[ReviewRow] = []
    for b in broadcasts:
        if has_date_prefix(b.title):
            continue
        if matches_any(b.title, base_titles):
            continue
        start = parse_iso_utc(b.start_iso)
        label = format_date_prefix(start, tz).removesuffix(" - ")
        rows.append(ReviewRow(b.video_id, label, b.title, b.start_iso, b.duration_seconds))
    rows.sort(key=lambda r: r.start_iso)
    return rows


def decide(
    broadcasts: list[Broadcast],
    base_titles: list[str],
    tz: str,
    window_days: int | None = None,
    now_utc: datetime | None = None,
    min_worship_seconds: int | None = None,
) -> list[Change]:
    """Return retitle changes — always lossless: prepend the stream's own date,
    keep the existing title.

    A dateless livestream qualifies if its title is on the ``base_titles`` allowlist
    OR (when ``min_worship_seconds`` is set) it runs at least that long — a full
    worship service, regardless of how it was titled. Short streams (sermon clips,
    test streams, ``choir``) and anything already dated are left untouched.

    If window_days is set, only streams whose start time is within the last
    window_days (relative to now_utc, default current UTC time) are considered.
    """
    changes: list[Change] = []
    ref = now_utc or datetime.now(UTC)
    for b in broadcasts:
        if has_date_prefix(b.title):
            continue
        long_enough = (
            min_worship_seconds is not None
            and b.duration_seconds is not None
            and b.duration_seconds >= min_worship_seconds
        )
        if not (matches_any(b.title, base_titles) or long_enough):
            continue
        start = parse_iso_utc(b.start_iso)
        if window_days is not None and start < ref - timedelta(days=window_days):
            continue
        prefix = format_date_prefix(start, tz)
        changes.append(Change(b.video_id, b.title, prefix + b.title))
    return changes
