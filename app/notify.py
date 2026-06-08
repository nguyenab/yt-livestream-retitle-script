from __future__ import annotations

from app.jobs import JobReport
from app.retitle import ReviewRow

_MAX_LISTED = 25


def _url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"


def _dur_label(seconds: int | None) -> str:
    if seconds is None:
        return "?"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def format_review(rows: list[ReviewRow]) -> str:
    """Human-readable review list for the Actions log. Duration is shown so the
    >=1h worship-service cutoff is easy to eyeball.
    """
    lines = [
        f"Unmatched livestreams (review candidates): {len(rows)}",
        "(not already dated, not on the BASE_TITLES allowlist — no changes made)",
        "",
    ]
    lines.extend(
        f"{r.date_label}  |  {_dur_label(r.duration_seconds)}  |  {_url(r.video_id)}  |  {r.title}"
        for r in rows
    )
    return "\n".join(lines)


def review_csv_rows(rows: list[ReviewRow]) -> list[list[str]]:
    """Rows for the downloadable CSV artifact (header first). Standalone weekday and
    duration_min columns make it trivial to filter (e.g. non-Sunday, or under 60 min).
    """
    out = [
        [
            "weekday",
            "broadcast_date_pacific",
            "duration_min",
            "video_id",
            "url",
            "current_title",
            "start_utc",
        ]
    ]
    for r in rows:
        weekday = r.date_label.split(",", 1)[0]
        dur_min = "" if r.duration_seconds is None else str(round(r.duration_seconds / 60))
        out.append(
            [weekday, r.date_label, dur_min, r.video_id, _url(r.video_id), r.title, r.start_iso]
        )
    return out


def format_report(title: str, report: JobReport) -> str:
    lines = [
        title,
        f"Scanned: {report.scanned}",
        f"Changed: {report.changed}",
        f"Skipped: {report.skipped}",
    ]
    if report.dry_run:
        lines.append("(DRY_RUN — no changes written)")
    for _vid, new in report.changes[:_MAX_LISTED]:
        lines.append(f"• {new}")
    extra = len(report.changes) - _MAX_LISTED
    if extra > 0:
        lines.append(f"…and {extra} more")
    if report.failures:
        lines.append(f"Failures ({len(report.failures)}):")
        lines.extend(f"⚠ {f}" for f in report.failures[:10])
    return "\n".join(lines)
