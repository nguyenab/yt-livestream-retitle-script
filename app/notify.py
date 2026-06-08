from __future__ import annotations

from app.jobs import JobReport
from app.retitle import ReviewRow

_MAX_LISTED = 25


def _url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"


def format_review(rows: list[ReviewRow]) -> str:
    """Human-readable review list for the Actions log."""
    lines = [
        f"Unmatched livestreams (review candidates): {len(rows)}",
        "(not already dated, not on the BASE_TITLES allowlist — no changes made)",
        "",
    ]
    lines.extend(f"{r.date_label}  |  {_url(r.video_id)}  |  {r.title}" for r in rows)
    return "\n".join(lines)


def review_csv_rows(rows: list[ReviewRow]) -> list[list[str]]:
    """Rows for the downloadable CSV artifact (header first). A standalone weekday
    column makes it trivial to filter out non-Sunday streams in a spreadsheet.
    """
    out = [["weekday", "broadcast_date_pacific", "video_id", "url", "current_title", "start_utc"]]
    for r in rows:
        weekday = r.date_label.split(",", 1)[0]
        out.append([weekday, r.date_label, r.video_id, _url(r.video_id), r.title, r.start_iso])
    return out


def format_report(title: str, report: JobReport) -> str:
    lines = [
        title,
        f"Scanned: {report.scanned}",
        f"Changed: {report.changed}",
        f"Skipped: {report.skipped}",
    ]
    replaced = sum(1 for ch in report.changes if len(ch) > 2 and ch[2])
    if replaced:
        lines.append(f"Retitled (title replaced): {replaced}")
    if report.dry_run:
        lines.append("(DRY_RUN — no changes written)")
    for _vid, new, *rest in report.changes[:_MAX_LISTED]:
        marker = "✎" if (rest and rest[0]) else "•"
        lines.append(f"{marker} {new}")
    extra = len(report.changes) - _MAX_LISTED
    if extra > 0:
        lines.append(f"…and {extra} more")
    if report.failures:
        lines.append(f"Failures ({len(report.failures)}):")
        lines.extend(f"⚠ {f}" for f in report.failures[:10])
    return "\n".join(lines)
