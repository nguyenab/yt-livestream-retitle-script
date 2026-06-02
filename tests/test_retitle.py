from datetime import datetime, timezone

from app.retitle import Broadcast, Change, decide

BASE = "Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển"
TZ = "America/Los_Angeles"
NOW = datetime(2026, 5, 11, 0, 0, tzinfo=timezone.utc)  # Sunday night UTC


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
