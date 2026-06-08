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
    force_ids: frozenset[str] | None = None,
) -> list[Change]:
    """Return retitle changes for livestreams.

    Default (safe) behavior: a dateless title on the ``base_titles`` allowlist gets
    its date prefix prepended; everything else is left alone. We never guess that an
    arbitrary non-matching title is a mis-titled worship stream — many livestreams
    legitimately have their own titles (weekday studies, special events).

    Curated repair: a video whose id is in ``force_ids`` is one you've explicitly
    confirmed was mis-titled. It is rewritten to ``<date> - <canonical>`` using its
    own broadcast date, regardless of its current title or any existing date prefix.
    This is idempotent (skipped once the title already equals the target) and exempt
    from the recency window, since you asked for it by id.

    If window_days is set, only allowlist matches whose start time is within the last
    window_days (relative to now_utc, default current UTC time) are considered;
    ``force_ids`` repairs are not subject to it.
    """
    changes: list[Change] = []
    ref = now_utc or datetime.now(UTC)
    force_ids = force_ids or frozenset()
    for b in broadcasts:
        start = parse_iso_utc(b.start_iso)
        prefix = format_date_prefix(start, tz)
        if b.video_id in force_ids:
            if canonical is None:
                continue
            target = prefix + canonical
            if b.title != target:
                changes.append(Change(b.video_id, b.title, target, replaced=True))
            continue
        if has_date_prefix(b.title):
            continue
        if not matches_any(b.title, base_titles):
            continue
        if window_days is not None and start < ref - timedelta(days=window_days):
            continue
        changes.append(Change(b.video_id, b.title, prefix + b.title, replaced=False))
    return changes
