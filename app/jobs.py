from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app import youtube
from app.retitle import Broadcast, ReviewRow, decide, find_unmatched

log = logging.getLogger(__name__)


@dataclass
class JobReport:
    scanned: int = 0
    changed: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)
    changes: list[tuple[str, str]] = field(default_factory=list)  # (video_id, new_title)
    dry_run: bool = False


def _collect(sources) -> list[Broadcast]:
    """Run each source listing thunk, union the rows, dedupe by video_id (first wins)."""
    seen: set[str] = set()
    broadcasts: list[Broadcast] = []
    for source in sources:
        for vid, title, start in source():
            if vid in seen:
                continue
            seen.add(vid)
            broadcasts.append(Broadcast(vid, title, start))
    return broadcasts


def _with_durations(service, broadcasts: list[Broadcast]) -> list[Broadcast]:
    """Backfill each broadcast's video length via a single batched videos.list call."""
    if not broadcasts:
        return broadcasts
    durations = youtube.fetch_durations(service, [b.video_id for b in broadcasts])
    return [
        Broadcast(b.video_id, b.title, b.start_iso, durations.get(b.video_id))
        for b in broadcasts
    ]


def _execute(service, config, broadcasts, window_days, canonical=None) -> JobReport:
    changes = decide(
        broadcasts,
        config.base_titles,
        config.timezone,
        window_days,
        canonical=canonical,
        canonicalize_ids=config.canonicalize_ids,
    )
    report = JobReport(
        scanned=len(broadcasts),
        skipped=len(broadcasts) - len(changes),
        dry_run=config.dry_run,
    )
    for ch in changes:
        try:
            if config.dry_run:
                log.info("[DRY_RUN] would retitle %s -> %s", ch.video_id, ch.new_title)
            else:
                snippet = youtube.get_video_snippet(service, ch.video_id)
                if snippet is None:
                    raise RuntimeError("video not found")
                youtube.update_title(service, ch.video_id, snippet, ch.new_title)
                log.info("retitled %s -> %s", ch.video_id, ch.new_title)
            report.changed += 1
            report.changes.append((ch.video_id, ch.new_title))
        except Exception as e:  # noqa: BLE001 - one failure must not abort the batch
            log.exception("failed to retitle %s", ch.video_id)
            report.failures.append(f"{ch.video_id}: {e}")
    return report


def run_job(service, config, statuses, window_days) -> JobReport:
    """Single-source run over liveBroadcasts.list (back-compat / diagnostic path).

    Matches-only (no duration gate), so it never needs to fetch video lengths.
    """
    broadcasts = _collect([lambda: youtube.list_broadcasts(service, statuses)])
    return _execute(service, config, broadcasts, window_days)


def weekly_job(service, config) -> JobReport:
    # liveBroadcasts catches upcoming/active streams; the uploads playlist catches
    # recently-completed ones a persistent stream key may not surface there.
    sources = [
        lambda: youtube.list_broadcasts(service, ["all"]),
        lambda: youtube.list_livestreams_via_uploads(service),
    ]
    broadcasts = _collect(sources)
    return _execute(
        service,
        config,
        broadcasts,
        config.recent_window_days,
        canonical=config.base_titles[0],
    )


def restore_titles(service, config, overrides) -> JobReport:
    """Set each ``(video_id, title)`` verbatim — a one-time un-do for titles a run
    changed that it shouldn't have. Idempotent in practice (re-setting the same title
    is harmless); continues past per-video failures like the retitle jobs.
    """
    report = JobReport(scanned=len(overrides), dry_run=config.dry_run)
    for vid, title in overrides:
        try:
            if config.dry_run:
                log.info("[DRY_RUN] would restore %s -> %s", vid, title)
            else:
                snippet = youtube.get_video_snippet(service, vid)
                if snippet is None:
                    raise RuntimeError("video not found")
                youtube.update_title(service, vid, snippet, title)
                log.info("restored %s -> %s", vid, title)
            report.changed += 1
            report.changes.append((vid, title))
        except Exception as e:  # noqa: BLE001 - one failure must not abort the batch
            log.exception("failed to restore %s", vid)
            report.failures.append(f"{vid}: {e}")
    report.skipped = report.scanned - report.changed
    return report


def review_unmatched(service, config) -> list[ReviewRow]:
    """Read-only scan of full history for livestreams worth a human look. No changes."""
    sources = [
        lambda: youtube.list_livestreams_via_uploads(service),
        lambda: youtube.list_broadcasts(service, ["completed"]),
    ]
    broadcasts = _with_durations(service, _collect(sources))
    return find_unmatched(broadcasts, config.base_titles, config.timezone)


def backdate_all(service, config) -> JobReport:
    # uploads playlist is the most reliable source for completed history; union with
    # completed liveBroadcasts as belt-and-suspenders, deduped by video id.
    sources = [
        lambda: youtube.list_livestreams_via_uploads(service),
        lambda: youtube.list_broadcasts(service, ["completed"]),
    ]
    broadcasts = _collect(sources)
    return _execute(
        service,
        config,
        broadcasts,
        None,
        canonical=config.base_titles[0],
    )
