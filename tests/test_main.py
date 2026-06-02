from dataclasses import dataclass

import app.main as main


@dataclass
class FakeCfg:
    telegram_chat_id: str = "123"
    base_titles: tuple = ("Worship Service",)
    timezone: str = "America/Los_Angeles"
    recent_window_days: int = 7
    dry_run: bool = False


def test_handle_command_status(monkeypatch):
    sent = []
    ctx = main.Context(
        config=FakeCfg(),
        service=object(),
        scheduler=None,
        started_at="2026-05-10T00:00:00Z",
        send=lambda text: sent.append(text),
        next_run=lambda: "2026-05-17 18:00 PDT",
    )
    main.handle_command(ctx, chat_id="123", text="/status")
    assert any("Status: running" in m for m in sent)


def test_handle_command_ignores_unauthorized_chat():
    sent = []
    ctx = main.Context(
        config=FakeCfg(),
        service=object(),
        scheduler=None,
        started_at="x",
        send=lambda text: sent.append(text),
        next_run=lambda: "x",
    )
    main.handle_command(ctx, chat_id="999", text="/status")
    assert sent == []


def test_handle_command_help():
    sent = []
    ctx = main.Context(
        config=FakeCfg(),
        service=object(),
        scheduler=None,
        started_at="x",
        send=lambda text: sent.append(text),
        next_run=lambda: "x",
    )
    main.handle_command(ctx, chat_id="123", text="/help")
    assert any("/status" in m and "/backdate" in m for m in sent)


def test_handle_command_run_triggers_weekly(monkeypatch):
    sent = []
    called = {}
    monkeypatch.setattr(main, "weekly_job", lambda svc, cfg: called.setdefault("weekly", True) or _Report())
    ctx = main.Context(
        config=FakeCfg(),
        service=object(),
        scheduler=None,
        started_at="x",
        send=lambda text: sent.append(text),
        next_run=lambda: "x",
    )
    main.handle_command(ctx, chat_id="123", text="/run")
    assert called.get("weekly") is True


class _Report:
    scanned = 0
    changed = 0
    skipped = 0
    dry_run = False
    changes = []
    failures = []


def test_drain_pending_updates_returns_next_offset(monkeypatch):
    monkeypatch.setattr(
        main.telegram,
        "get_updates",
        lambda token, offset=None, timeout=0: [{"update_id": 10}, {"update_id": 11}],
    )
    assert main._drain_pending_updates("T") == 12


def test_drain_pending_updates_none_when_empty(monkeypatch):
    monkeypatch.setattr(
        main.telegram, "get_updates", lambda token, offset=None, timeout=0: []
    )
    assert main._drain_pending_updates("T") is None


def test_drain_pending_updates_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(main.telegram, "get_updates", boom)
    assert main._drain_pending_updates("T") is None
