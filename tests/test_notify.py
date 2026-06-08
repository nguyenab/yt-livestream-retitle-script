from app.jobs import JobReport
from app.notify import format_report, format_review, review_csv_rows
from app.retitle import ReviewRow


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


def test_format_review_lists_candidates():
    rows = [ReviewRow("abc", "Friday, May 8th, 2026", "Friday Bible Study", "2026-05-08T18:00:00Z")]
    text = format_review(rows)
    assert "review candidates): 1" in text
    assert "Friday, May 8th, 2026" in text
    assert "youtu.be/abc" in text
    assert "Friday Bible Study" in text


def test_format_review_handles_empty():
    assert "0" in format_review([])


def test_review_csv_rows_header_and_shape():
    rows = [ReviewRow("abc", "Friday, May 8th, 2026", "Friday Bible Study", "2026-05-08T18:00:00Z")]
    out = review_csv_rows(rows)
    assert out[0] == [
        "weekday",
        "broadcast_date_pacific",
        "video_id",
        "url",
        "current_title",
        "start_utc",
    ]
    assert out[1] == [
        "Friday",
        "Friday, May 8th, 2026",
        "abc",
        "https://youtu.be/abc",
        "Friday Bible Study",
        "2026-05-08T18:00:00Z",
    ]
