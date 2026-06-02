from dataclasses import dataclass

import app.jobs as jobs
from app.jobs import run_job


@dataclass
class FakeCfg:
    base_titles: list
    timezone: str = "America/Los_Angeles"
    recent_window_days: int = 7
    dry_run: bool = False


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
