from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app import youtube
from app.retitle import Broadcast, decide

log = logging.getLogger(__name__)


@dataclass
class JobReport:
    scanned: int = 0
    changed: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)
    changes: list[tuple[str, str]] = field(default_factory=list)  # (video_id, new_title)
    dry_run: bool = False


def run_job(service, config, statuses, window_days) -> JobReport:
    raw = youtube.list_broadcasts(service, statuses)
    broadcasts = [Broadcast(vid, title, start) for vid, title, start in raw]
    changes = decide(broadcasts, config.base_titles, config.timezone, window_days)
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


def weekly_job(service, config) -> JobReport:
    return run_job(service, config, statuses=["all"], window_days=config.recent_window_days)


def backdate_all(service, config) -> JobReport:
    return run_job(service, config, statuses=["completed"], window_days=None)
