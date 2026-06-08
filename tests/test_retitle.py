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


# --- curated canonicalize list: normalise listed ids to "<date> - <canonical>" ---


def test_decide_unlisted_nonmatching_left_alone():
    # We never guess: a non-matching title not on the canonicalize list is untouched.
    b = Broadcast("v", "Some Sermon Title - Mục Sư", "2026-05-10T18:00:00Z")
    assert decide([b], [BASE], TZ, canonical=BASE) == []
    assert decide([b], [BASE], TZ, canonical=BASE, canonicalize_ids=frozenset({"other"})) == []


def test_decide_canonicalize_id_overwrites_sermon_title():
    b = Broadcast("v", "Stand Firm / Đứng vững - Mục Sư", "2026-05-10T18:00:00Z")
    changes = decide([b], [BASE], TZ, canonical=BASE, canonicalize_ids=frozenset({"v"}))
    assert changes == [
        Change("v", "Stand Firm / Đứng vững - Mục Sư", f"Sunday, May 10th, 2026 - {BASE}")
    ]


def test_decide_canonicalize_id_overwrites_already_dated_title():
    # The partial-run case: a stream already dated with sermon text is normalised.
    dated_sermon = "Sunday, May 10th, 2026 - Stand Firm - Mục Sư"
    b = Broadcast("v", dated_sermon, "2026-05-10T18:00:00Z")
    changes = decide([b], [BASE], TZ, canonical=BASE, canonicalize_ids=frozenset({"v"}))
    assert changes == [Change("v", dated_sermon, f"Sunday, May 10th, 2026 - {BASE}")]


def test_decide_canonicalize_id_is_idempotent():
    b = Broadcast("v", f"Sunday, May 10th, 2026 - {BASE}", "2026-05-10T18:00:00Z")
    assert decide([b], [BASE], TZ, canonical=BASE, canonicalize_ids=frozenset({"v"})) == []


def test_decide_matched_keeps_title_even_with_canonicalize_configured():
    # An allowlist match not on the list keeps its title (date-only), not overwritten.
    b = Broadcast("v", BASE, "2026-05-10T18:00:00Z")
    changes = decide([b], [BASE], TZ, canonical=BASE, canonicalize_ids=frozenset({"other"}))
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


def test_decide_skips_keep_title_over_100_chars():
    # Keep-title path: a source title that, once dated, exceeds 100 chars is skipped
    # rather than emitted (YouTube would reject it).
    long_title = "x" * 90  # 90 + ~27 date prefix > 100
    b = Broadcast("v", long_title, "2026-05-10T18:00:00Z")
    assert decide([b], [long_title], TZ) == []


def test_decide_canonical_fits_under_limit():
    # Canonical normalisation keeps every title well under the limit even from a long source.
    b = Broadcast("v", "y" * 95, "2026-05-10T18:00:00Z")
    changes = decide([b], [BASE], TZ, canonical=BASE, canonicalize_ids=frozenset({"v"}))
    assert len(changes) == 1
    assert len(changes[0].new_title) <= 100


def test_decide_protected_ids_never_touched():
    # A video in a protected playlist is skipped even if it'd otherwise be retitled.
    matched = Broadcast("p1", BASE, "2026-05-10T18:00:00Z")
    listed = Broadcast("p2", "Sermon - Mục Sư", "2026-05-10T18:00:00Z")
    out = decide(
        [matched, listed], [BASE], TZ, canonical=BASE,
        canonicalize_ids=frozenset({"p2"}), protected_ids=frozenset({"p1", "p2"}),
    )
    assert out == []
