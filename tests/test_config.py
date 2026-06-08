import pytest

from app.config import load_config

REQUIRED = {
    "YOUTUBE_CLIENT_ID": "cid",
    "YOUTUBE_CLIENT_SECRET": "secret",
    "YOUTUBE_REFRESH_TOKEN": "rt",
    "TELEGRAM_BOT_TOKEN": "bt",
    "TELEGRAM_CHAT_ID": "123",
    "BASE_TITLES": "Title A || Title B",
}


def _set(monkeypatch, **overrides):
    env = {**REQUIRED, **overrides}
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_load_config_parses_base_titles(monkeypatch):
    _set(monkeypatch)
    cfg = load_config()
    assert cfg.base_titles == ["Title A", "Title B"]


def test_load_config_defaults(monkeypatch):
    _set(monkeypatch)
    cfg = load_config()
    assert cfg.timezone == "America/Los_Angeles"
    assert cfg.recent_window_days == 7
    assert cfg.dry_run is False


def test_load_config_dry_run_true(monkeypatch):
    _set(monkeypatch, DRY_RUN="true")
    assert load_config().dry_run is True


def test_load_config_canonicalize_ids_default_empty(monkeypatch):
    _set(monkeypatch, CANONICALIZE_IDS_FILE="/nonexistent/path/ids.txt")
    assert load_config().canonicalize_ids == frozenset()


def test_load_config_reads_canonicalize_ids_file(monkeypatch, tmp_path):
    f = tmp_path / "ids.txt"
    f.write_text("# header\n\nabc123  # a sermon-retitled service\nDEF_456\n", encoding="utf-8")
    _set(monkeypatch, CANONICALIZE_IDS_FILE=str(f))
    assert load_config().canonicalize_ids == frozenset({"abc123", "DEF_456"})


def test_load_config_missing_required_raises(monkeypatch):
    _set(monkeypatch)
    monkeypatch.delenv("YOUTUBE_CLIENT_ID")
    with pytest.raises(ValueError, match="YOUTUBE_CLIENT_ID"):
        load_config()
