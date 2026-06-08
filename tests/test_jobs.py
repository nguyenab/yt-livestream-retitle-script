from dataclasses import dataclass

import app.jobs as jobs
from app.jobs import run_job


@dataclass
class FakeCfg:
    base_titles: list
    timezone: str = "America/Los_Angeles"
    recent_window_days: int = 7
    dry_run: bool = False
    force_retitle_ids: frozenset = frozenset()


BASE = "Worship Service"


def _patch_list(monkeypatch, rows):
    monkeypatch.setattr(jobs.youtube, "list_broadcasts", lambda svc, statuses: rows)


def test_run_job_applies_changes(monkeypatch):
    rows = [("v1", BASE, "2026-05-10T18:00:00Z")]
    _patch_list(monkeypatch, rows)
    monkeypatch.setattr(jobs.youtube, "get_video_snippet", lambda svc, vid: {"title": BASE, "categoryId": "22"})
    calls = []
    monkeypatch.setattr(jobs.youtube, "update_title", lambda svc, vid, snip, new: calls.append((vid, new)))
    report = run_job(object(), FakeCfg([BASE]), ["all"], window_days=None)
    assert report.changed == 1
    assert calls == [("v1", f"Sunday, May 10th, 2026 - {BASE}")]
    assert report.failures == []


def test_run_job_dry_run_does_not_update(monkeypatch):
    rows = [("v1", BASE, "2026-05-10T18:00:00Z")]
    _patch_list(monkeypatch, rows)
    called = []
    monkeypatch.setattr(jobs.youtube, "update_title", lambda *a, **k: called.append(a))
    report = run_job(object(), FakeCfg([BASE], dry_run=True), ["all"], window_days=None)
    assert report.changed == 1
    assert called == []


def test_run_job_collects_failures(monkeypatch):
    rows = [("v1", BASE, "2026-05-10T18:00:00Z")]
    _patch_list(monkeypatch, rows)
    monkeypatch.setattr(jobs.youtube, "get_video_snippet", lambda svc, vid: {"title": BASE, "categoryId": "22"})

    def boom(*a, **k):
        raise RuntimeError("api down")

    monkeypatch.setattr(jobs.youtube, "update_title", boom)
    report = run_job(object(), FakeCfg([BASE]), ["all"], window_days=None)
    assert report.changed == 0
    assert len(report.failures) == 1
    assert "api down" in report.failures[0]


def test_run_job_no_matches(monkeypatch):
    _patch_list(monkeypatch, [("v1", "Unrelated", "2026-05-10T18:00:00Z")])
    report = run_job(object(), FakeCfg([BASE]), ["all"], window_days=None)
    assert report.changed == 0
    assert report.scanned == 1


def test_backdate_force_id_replaces_non_matching(monkeypatch):
    # A confirmed-mis-titled stream (in force_retitle_ids) is overwritten with canonical,
    # while a sibling non-matching stream not on the list is left untouched.
    monkeypatch.setattr(
        jobs.youtube,
        "list_livestreams_via_uploads",
        lambda svc: [
            ("bad", "Romans 8:28 - Sermon", "2024-01-07T18:00:00Z"),
            ("other", "Friday Bible Study", "2024-01-12T18:00:00Z"),
        ],
    )
    monkeypatch.setattr(jobs.youtube, "list_broadcasts", lambda svc, statuses: [])
    monkeypatch.setattr(
        jobs.youtube, "get_video_snippet", lambda svc, vid: {"title": "x", "categoryId": "22"}
    )
    applied = []
    monkeypatch.setattr(
        jobs.youtube, "update_title", lambda svc, vid, snip, new: applied.append((vid, new))
    )
    cfg = FakeCfg([BASE], force_retitle_ids=frozenset({"bad"}))
    report = jobs.backdate_all(object(), cfg)
    assert applied == [("bad", f"Sunday, January 7th, 2024 - {BASE}")]
    assert report.changed == 1


def test_weekly_job_unions_sources_and_dedupes(monkeypatch):
    # liveBroadcasts and uploads-playlist both report v1; v1 must be counted once.
    monkeypatch.setattr(
        jobs.youtube, "list_broadcasts", lambda svc, statuses: [("v1", BASE, "2026-05-10T18:00:00Z")]
    )
    monkeypatch.setattr(
        jobs.youtube,
        "list_livestreams_via_uploads",
        lambda svc: [("v1", BASE, "2026-05-10T18:00:00Z"), ("v2", BASE, "2026-05-10T18:00:00Z")],
    )
    monkeypatch.setattr(jobs.youtube, "get_video_snippet", lambda svc, vid: {"title": BASE, "categoryId": "22"})
    applied = []
    monkeypatch.setattr(jobs.youtube, "update_title", lambda svc, vid, snip, new: applied.append(vid))
    # wide window so the fixed dates aren't filtered out by recency
    report = jobs.weekly_job(object(), FakeCfg([BASE], recent_window_days=3650))
    assert report.scanned == 2
    assert sorted(applied) == ["v1", "v2"]


def test_backdate_all_unions_uploads_and_completed(monkeypatch):
    monkeypatch.setattr(
        jobs.youtube,
        "list_livestreams_via_uploads",
        lambda svc: [("v1", BASE, "2024-01-07T18:00:00Z")],
    )
    monkeypatch.setattr(
        jobs.youtube,
        "list_broadcasts",
        lambda svc, statuses: [("v1", BASE, "2024-01-07T18:00:00Z"), ("v2", BASE, "2024-01-14T18:00:00Z")],
    )
    monkeypatch.setattr(jobs.youtube, "get_video_snippet", lambda svc, vid: {"title": BASE, "categoryId": "22"})
    applied = []
    monkeypatch.setattr(jobs.youtube, "update_title", lambda svc, vid, snip, new: applied.append(vid))
    report = jobs.backdate_all(object(), FakeCfg([BASE]))
    assert report.scanned == 2  # v1 deduped across the two sources
    assert sorted(applied) == ["v1", "v2"]
