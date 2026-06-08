from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    youtube_client_id: str
    youtube_client_secret: str
    youtube_refresh_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    base_titles: list[str]
    timezone: str
    recent_window_days: int
    dry_run: bool
    log_level: str
    canonicalize_ids: frozenset[str]


def _require(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise ValueError(f"Missing required env var: {name}")
    return val


def _load_ids(path: str) -> frozenset[str]:
    """Read a committed list of video ids (one per line, ``#`` comments ok).

    Missing file -> empty set. Used for the curated canonicalize list — the services a
    team member renamed with sermon text. Adding an id is a deliberate, reviewable edit.
    """
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return frozenset()
    ids = {tok for line in lines if (tok := line.split("#", 1)[0].strip())}
    return frozenset(ids)


def load_config() -> Config:
    load_dotenv()
    base = _require("BASE_TITLES")
    return Config(
        youtube_client_id=_require("YOUTUBE_CLIENT_ID"),
        youtube_client_secret=_require("YOUTUBE_CLIENT_SECRET"),
        youtube_refresh_token=_require("YOUTUBE_REFRESH_TOKEN"),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require("TELEGRAM_CHAT_ID"),
        base_titles=[t.strip() for t in base.split("||") if t.strip()],
        timezone=os.getenv("TIMEZONE", "America/Los_Angeles").strip(),
        recent_window_days=int(os.getenv("RECENT_WINDOW_DAYS", "7")),
        dry_run=os.getenv("DRY_RUN", "false").strip().lower() in ("1", "true", "yes"),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        canonicalize_ids=_load_ids(
            os.getenv("CANONICALIZE_IDS_FILE", "canonicalize_ids.txt").strip()
        ),
    )
