from app.jobs import JobReport
from app.notify import format_report


def test_format_report_summary_and_changes():
    r = JobReport(scanned=5, changed=2, skipped=3, dry_run=False)
    r.changes = [("v1", "Sunday, May 10th, 2026 - Worship Service", False)]
    text = format_report("Weekly run", r)
    assert "Weekly run" in text
    assert "Scanned: 5" in text
    assert "Changed: 2" in text
    assert "Sunday, May 10th, 2026 - Worship Service" in text


def test_format_report_marks_replaced_titles():
    # Replaced (overwritten) titles are flagged distinctly from prefixed ones so the
    # reader can eyeball every overwrite for mistakes.
    r = JobReport(scanned=2, changed=2, skipped=0, dry_run=False)
    r.changes = [
        ("v1", "Sunday, May 10th, 2026 - Worship Service", False),
        ("v2", "Sunday, May 3rd, 2026 - Worship Service", True),
    ]
    text = format_report("Backdate", r)
    assert "Retitled (title replaced): 1" in text
    # the replaced entry is marked differently from the prefixed one
    assert "✎ Sunday, May 3rd, 2026 - Worship Service" in text
    assert "• Sunday, May 10th, 2026 - Worship Service" in text


def test_format_report_marks_dry_run_and_failures():
    r = JobReport(scanned=1, changed=0, skipped=1, dry_run=True)
    r.failures = ["v9: boom"]
    text = format_report("Backdate", r)
    assert "DRY_RUN" in text
    assert "v9: boom" in text
