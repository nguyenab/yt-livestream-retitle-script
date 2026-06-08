from datetime import UTC, datetime, timedelta

from app.retitle import Broadcast, Change, decide

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


def test_decide_replaces_non_matching_with_canonical():
    # A mis-titled worship stream (sermon text as the title) gets date + canonical.
    b = Broadcast("vid1", "Romans 8:28 - The Goodness of God", "2026-05-10T18:00:00Z")
    changes = decide([b], [BASE], TZ, canonical=BASE)
    assert changes == [
        Change(
            "vid1",
            "Romans 8:28 - The Goodness of God",
            f"Sunday, May 10th, 2026 - {BASE}",
            replaced=True,
        )
    ]


def test_decide_keeps_matching_title_even_with_canonical():
    # A title already on the allowlist is preserved (just dated), not overwritten.
    b = Broadcast("vid1", BASE, "2026-05-10T18:00:00Z")
    changes = decide([b], [BASE], TZ, canonical=BASE)
    assert changes == [Change("vid1", BASE, f"Sunday, May 10th, 2026 - {BASE}", replaced=False)]


def test_decide_replacement_respects_window():
    old = Broadcast("old", "Some Sermon", "2026-04-01T18:00:00Z")
    recent = Broadcast("new", "Other Sermon", "2026-05-10T18:00:00Z")
    changes = decide([old, recent], [BASE], TZ, window_days=7, now_utc=NOW, canonical=BASE)
    assert [c.video_id for c in changes] == ["new"]


def test_decide_replacement_skips_already_dated():
    dated = "Sunday, May 10th, 2026 - Romans 8:28"
    b = Broadcast("vid1", dated, "2026-05-10T18:00:00Z")
    assert decide([b], [BASE], TZ, canonical=BASE) == []


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
