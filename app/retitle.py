from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.dates import format_date_prefix, has_date_prefix, parse_iso_utc
from app.matching import matches_any

MAX_TITLE_LEN = 100  # YouTube rejects titles longer than this ("invalidTitle")


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
    canonical: str | None = None,
    min_worship_seconds: int | None = None,
) -> list[Change]:
    """Return retitle changes for worship-service livestreams.

    A stream **qualifies** if its title is on the ``base_titles`` allowlist OR (when
    ``min_worship_seconds`` is set) it runs at least that long — a full worship
    service, however it was titled. Short streams (sermon clips, test streams,
    ``choir``) never qualify.

    Target title:
    - With ``canonical`` set, a qualifying stream is normalised to
      ``<date> - <canonical>`` — its own broadcast date plus the standard service
      title. This overwrites whatever was there (sermon text, an old bracketed date),
      keeping every service titled identically and safely under YouTube's 100-char
      limit. Already-correct titles are skipped (idempotent), including ones that
      already carry a date prefix.
    - Without ``canonical`` (the ``run_job`` diagnostic path), the existing title is
      kept and only the date prefix is prepended; already-dated titles are skipped.

    If window_days is set, only streams whose start time is within the last
    window_days (relative to now_utc, default current UTC time) are considered.
    """
    changes: list[Change] = []
    ref = now_utc or datetime.now(UTC)
    for b in broadcasts:
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
        if canonical is not None:
            target = prefix + canonical
        else:
            if has_date_prefix(b.title):
                continue
            target = prefix + b.title
        if b.title == target or len(target) > MAX_TITLE_LEN:
            # Skip no-ops and anything YouTube would reject for length. With canonical
            # set this never trips (date + standard title is well under the limit);
            # it only guards the keep-title path against over-long source titles.
            continue
        changes.append(Change(b.video_id, b.title, target))
    return changes
