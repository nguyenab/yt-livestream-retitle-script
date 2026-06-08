from datetime import UTC, datetime, timedelta

from app.retitle import Broadcast, Change, ReviewRow, decide, find_unmatched

BASE = "Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển"
TZ = "America/Los_Angeles"
NOW = datetime(2026, 5, 11, 0, 0, tzinfo=UTC)  # Sunday night UTC


def test_decide_prepends_date_to_matching_dateless():
    b = Broadcast("vid1", BASE, "2026-05-10T18:00:00Z")
    changes = decide([b], [BASE], TZ)
    assert changes == [Change("vid1", BASE, f"Sunday, May 10th, 2026 - {BASE}")]


def test_decide_skips_already_dated():
    dated = f"Sunday, May 10th, 2026 - {BASE}"
    b = Broadcast("vid1", dated, "2026-05-10T18:00:00Z")
    assert decide([b], [BASE], TZ) == []


def test_decide_skips_non_matching_title():
    b = Broadcast("vid1", "Random Stream", "2026-05-10T18:00:00Z")
    assert decide([b], [BASE], TZ) == []


def test_decide_no_threshold_ignores_duration():
    # Without min_worship_seconds it's matches-only; a long non-match is left alone.
    b = Broadcast("v", "Long non-match", "2026-05-10T18:00:00Z", 99999)
    assert decide([b], [BASE], TZ) == []


def test_decide_long_nonmatching_gets_dated_keeping_title():
    # A 70-min sermon-titled stream is a worship service -> date prefixed, title kept.
    b = Broadcast("v", "Stand Firm - Mục Sư", "2026-05-10T18:00:00Z", 70 * 60)
    changes = decide([b], [BASE], TZ, min_worship_seconds=3600)
    assert changes == [
        Change("v", "Stand Firm - Mục Sư", "Sunday, May 10th, 2026 - Stand Firm - Mục Sư")
    ]


def test_decide_short_nonmatching_left_alone():
    b = Broadcast("v", "Sermon clip", "2026-05-10T18:00:00Z", 20 * 60)
    assert decide([b], [BASE], TZ, min_worship_seconds=3600) == []


def test_decide_unknown_duration_nonmatching_left_alone():
    b = Broadcast("v", "Mystery", "2026-05-10T18:00:00Z", None)
    assert decide([b], [BASE], TZ, min_worship_seconds=3600) == []


def test_decide_long_respects_window():
    old = Broadcast("old", "Old long sermon", "2026-04-01T18:00:00Z", 70 * 60)
    recent = Broadcast("new", "New long sermon", "2026-05-10T18:00:00Z", 70 * 60)
    changes = decide(
        [old, recent], [BASE], TZ, window_days=7, now_utc=NOW, min_worship_seconds=3600
    )
    assert [c.video_id for c in changes] == ["new"]


def test_decide_matching_dated_regardless_of_duration():
    # An allowlist match is dated even if short — it doesn't depend on the threshold.
    b = Broadcast("v", BASE, "2026-05-10T18:00:00Z", 60)
    changes = decide([b], [BASE], TZ, min_worship_seconds=3600)
    assert changes == [Change("v", BASE, f"Sunday, May 10th, 2026 - {BASE}")]


def test_find_unmatched_excludes_dated_and_matching():
    rows = [
        Broadcast("m", BASE, "2026-05-10T18:00:00Z"),  # on allowlist -> exclude
        Broadcast("d", f"Sunday, May 10th, 2026 - {BASE}", "2026-05-10T18:00:00Z"),  # dated -> exclude
        Broadcast("u", "Friday Bible Study", "2026-05-08T18:00:00Z"),  # the odd one out -> include
    ]
    out = find_unmatched(rows, [BASE], TZ)
    assert out == [ReviewRow("u", "Friday, May 8th, 2026", "Friday Bible Study", "2026-05-08T18:00:00Z")]


def test_find_unmatched_sorted_by_broadcast_time():
    rows = [
        Broadcast("later", "Special Event", "2026-05-10T18:00:00Z"),
        Broadcast("earlier", "Guest Speaker", "2026-01-01T18:00:00Z"),
    ]
    out = find_unmatched(rows, [BASE], TZ)
    assert [r.video_id for r in out] == ["earlier", "later"]


def test_decide_window_excludes_old():
    old = Broadcast("old", BASE, "2026-04-01T18:00:00Z")
    recent = Broadcast("new", BASE, "2026-05-10T18:00:00Z")
    changes = decide([old, recent], [BASE], TZ, window_days=7, now_utc=NOW)
    assert [c.video_id for c in changes] == ["new"]


def test_decide_backdate_mode_includes_old():
    old = Broadcast("old", BASE, "2024-01-07T18:00:00Z")
    changes = decide([old], [BASE], TZ, window_days=None)
    assert len(changes) == 1
    assert changes[0].new_title.startswith("Sunday, January 7th, 2024 - ")


def test_decide_window_includes_stream_exactly_at_edge():
    now = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    edge_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")  # exactly 7 days back
    b = Broadcast("v1", BASE, edge_iso)
    changes = decide([b], [BASE], TZ, window_days=7, now_utc=now)
    assert [c.video_id for c in changes] == ["v1"]


def test_decide_window_excludes_stream_just_before_edge():
    now = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    before_iso = (now - timedelta(days=7, seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    b = Broadcast("v1", BASE, before_iso)
    changes = decide([b], [BASE], TZ, window_days=7, now_utc=now)
    assert changes == []
