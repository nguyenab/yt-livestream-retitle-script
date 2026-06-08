from __future__ import annotations

from app.jobs import JobReport

_MAX_LISTED = 25


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
