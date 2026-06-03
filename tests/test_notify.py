from app.jobs import JobReport
from app.notify import format_report


def test_format_report_summary_and_changes():
    r = JobReport(scanned=5, changed=2, skipped=3, dry_run=False)
    r.changes = [("v1", "Sunday, May 10th, 2026 - Worship Service")]
    text = format_report("Weekly run", r)
    assert "Weekly run" in text
    assert "Scanned: 5" in text
    assert "Changed: 2" in text
    assert "Sunday, May 10th, 2026 - Worship Service" in text


def test_format_report_marks_dry_run_and_failures():
    r = JobReport(scanned=1, changed=0, skipped=1, dry_run=True)
    r.failures = ["v9: boom"]
    text = format_report("Backdate", r)
    assert "DRY_RUN" in text
    assert "v9: boom" in text
