from app.jobs import JobReport
from app.notify import format_report, format_review, review_csv_rows
from app.retitle import ReviewRow


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


def test_format_review_lists_candidates_with_duration():
    rows = [ReviewRow("abc", "Friday, May 8th, 2026", "Friday Bible Study", "2026-05-08T18:00:00Z", 4200)]
    text = format_review(rows)
    assert "review candidates): 1" in text
    assert "Friday, May 8th, 2026" in text
    assert "1h10m" in text  # 4200s
    assert "youtu.be/abc" in text
    assert "Friday Bible Study" in text


def test_format_review_handles_empty():
    assert "0" in format_review([])


def test_review_csv_rows_header_and_shape():
    rows = [ReviewRow("abc", "Friday, May 8th, 2026", "Friday Bible Study", "2026-05-08T18:00:00Z", 4200)]
    out = review_csv_rows(rows)
    assert out[0] == [
        "weekday",
        "broadcast_date_pacific",
        "duration_min",
        "video_id",
        "url",
        "current_title",
        "start_utc",
    ]
    assert out[1] == [
        "Friday",
        "Friday, May 8th, 2026",
        "70",
        "abc",
        "https://youtu.be/abc",
        "Friday Bible Study",
        "2026-05-08T18:00:00Z",
    ]


def test_review_csv_rows_blank_duration_when_unknown():
    rows = [ReviewRow("abc", "Friday, May 8th, 2026", "x", "2026-05-08T18:00:00Z", None)]
    assert review_csv_rows(rows)[1][2] == ""
