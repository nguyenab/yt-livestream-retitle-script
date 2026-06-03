import app.main as main


def test_collect_diagnostics_gathers_both_sources(monkeypatch):
    monkeypatch.setattr(
        main.youtube, "list_broadcasts", lambda svc, statuses: [("v1", "A", "2026-05-10T18:00:00Z")]
    )
    monkeypatch.setattr(
        main.youtube,
        "list_livestreams_via_uploads",
        lambda svc: [("v2", "B", "2026-05-11T18:00:00Z")],
    )
    diag = main.collect_diagnostics(object())
    assert diag["liveBroadcasts (all)"] == [("v1", "A", "2026-05-10T18:00:00Z")]
    assert diag["uploads playlist (livestreams)"] == [("v2", "B", "2026-05-11T18:00:00Z")]
