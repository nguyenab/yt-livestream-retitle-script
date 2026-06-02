# YouTube Livestream Auto-Retitle Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python daemon on a VPS that prepends each YouTube livestream's own broadcast date (Pacific time) to its title — once for the full backlog and automatically every Sunday 18:00 Pacific — controlled and monitored via an existing Telegram bot.

**Architecture:** Small single-purpose modules under `app/`. Pure logic (`dates`, `matching`, `retitle`, `notify`) is network-free and fully unit-tested with TDD. Thin network wrappers (`youtube`, `telegram`) are mocked in tests. `main.py` wires an APScheduler weekly cron trigger and a Telegram long-poll command loop. systemd keeps it alive.

**Tech Stack:** Python 3.11+, google-api-python-client + google-auth(-oauthlib) (YouTube Data API v3), APScheduler, requests, python-dotenv, pytest.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/__init__.py` | Package marker |
| `app/dates.py` | UTC→Pacific conversion, ordinal date prefix, date-prefix regex (pure) |
| `app/matching.py` | Title normalization + match against base titles (pure) |
| `app/config.py` | Load + validate `.env` into a `Config` dataclass |
| `app/retitle.py` | `Broadcast`/`Change` types + `decide()` pure decision logic |
| `app/state.py` | Atomic JSON state read/write for `/status` |
| `app/youtube.py` | OAuth service, `list_broadcasts`, `get_video_snippet`, `update_title` |
| `app/telegram.py` | `send_message`, `get_updates` |
| `app/notify.py` | Format `JobReport` / status into Telegram text (pure) |
| `app/jobs.py` | `JobReport`, `run_job`, `weekly_job`, `backdate_all` |
| `app/main.py` | Logging, scheduler, Telegram command loop, startup notify, CLI |
| `get_token.py` | One-time OAuth bootstrap → prints refresh token |
| `tests/*` | Unit tests |
| `requirements.txt` | Runtime + dev deps |
| `deploy/yt-retitle.service` | systemd unit template |
| `docs/SETUP.md` | Google Cloud OAuth + VPS + Telegram setup |
| `CLAUDE.md` | `.env` reference + how to update on VPS |
| `.env.example` | Template env file |

---

## Task 0: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`
- Create: `pytest.ini`

- [ ] **Step 1: Create `requirements.txt`**

```text
google-api-python-client>=2.100
google-auth>=2.23
google-auth-oauthlib>=1.1
APScheduler>=3.10
requests>=2.31
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 2: Create empty package markers**

`app/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 4: Create venv and install**

Run:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt
```
Expected: installs without error.

- [ ] **Step 5: Verify pytest runs (no tests yet)**

Run: `.venv/bin/python -m pytest`
Expected: `no tests ran` (exit code 5) — acceptable.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/__init__.py tests/__init__.py pytest.ini
git commit -m "chore: project scaffolding and deps"
```

---

## Task 1: `app/dates.py` — date formatting & prefix detection

**Files:**
- Create: `app/dates.py`
- Test: `tests/test_dates.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_dates.py`:
```python
from datetime import datetime, timezone

from app.dates import (
    format_date_prefix,
    has_date_prefix,
    strip_date_prefix,
    parse_iso_utc,
    _ordinal,
)


def test_ordinals():
    assert _ordinal(1) == "st"
    assert _ordinal(2) == "nd"
    assert _ordinal(3) == "rd"
    assert _ordinal(4) == "th"
    assert _ordinal(11) == "th"
    assert _ordinal(12) == "th"
    assert _ordinal(13) == "th"
    assert _ordinal(21) == "st"
    assert _ordinal(22) == "nd"
    assert _ordinal(23) == "rd"
    assert _ordinal(31) == "st"


def test_format_date_prefix_pacific():
    # 2026-05-10 18:00 UTC -> 11:00 PDT, still May 10 (a Sunday)
    dt = datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc)
    assert format_date_prefix(dt, "America/Los_Angeles") == "Sunday, May 10th, 2026 - "


def test_format_date_prefix_crosses_day_in_pacific():
    # 2025-05-11 01:30 UTC -> 2025-05-10 18:30 PDT (Saturday)
    dt = datetime(2025, 5, 11, 1, 30, tzinfo=timezone.utc)
    assert format_date_prefix(dt, "America/Los_Angeles") == "Saturday, May 10th, 2025 - "


def test_has_and_strip_date_prefix():
    titled = "Sunday, May 10th, 2026 - Worship Service"
    assert has_date_prefix(titled) is True
    assert strip_date_prefix(titled) == "Worship Service"


def test_no_date_prefix():
    assert has_date_prefix("Worship Service") is False
    assert strip_date_prefix("Worship Service") == "Worship Service"


def test_parse_iso_utc():
    dt = parse_iso_utc("2025-05-11T01:30:00Z")
    assert dt == datetime(2025, 5, 11, 1, 30, tzinfo=timezone.utc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.dates'`

- [ ] **Step 3: Write `app/dates.py`**

```python
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

# Matches a leading "Weekday, Month Dayth, Year - " prefix.
DATE_PREFIX_RE = re.compile(
    r"^[A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th), \d{4} - "
)


def _ordinal(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def parse_iso_utc(ts: str) -> datetime:
    """Parse a YouTube ISO-8601 timestamp (e.g. '2025-05-11T01:30:00Z') as aware UTC."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def format_date_prefix(dt_utc: datetime, tz: str = "America/Los_Angeles") -> str:
    """Convert a UTC datetime to local tz and return 'Weekday, Month Dayth, Year - '."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    local = dt_utc.astimezone(ZoneInfo(tz))
    return f"{local.strftime('%A, %B')} {local.day}{_ordinal(local.day)}, {local.year} - "


def has_date_prefix(title: str) -> bool:
    return bool(DATE_PREFIX_RE.match(title))


def strip_date_prefix(title: str) -> str:
    return DATE_PREFIX_RE.sub("", title, count=1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dates.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/dates.py tests/test_dates.py
git commit -m "feat: date prefix formatting and detection"
```

---

## Task 2: `app/matching.py` — title normalization & matching

**Files:**
- Create: `app/matching.py`
- Test: `tests/test_matching.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_matching.py`:
```python
from app.matching import normalize, matches_any

BASE = "Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển"


def test_normalize_strips_diacritics_and_case():
    assert normalize("Lễ thờ phượng") == "le tho phuong"


def test_normalize_strips_date_prefix():
    assert normalize(f"Sunday, May 10th, 2026 - {BASE}") == normalize(BASE)


def test_normalize_collapses_whitespace():
    assert normalize("Worship   Service\n") == "worship service"


def test_matches_any_true_with_date_prefix():
    title = f"Sunday, May 10th, 2026 - {BASE}"
    assert matches_any(title, [BASE]) is True


def test_matches_any_true_case_insensitive():
    assert matches_any(BASE.upper(), [BASE]) is True


def test_matches_any_false_for_unrelated():
    assert matches_any("Some Random Video", [BASE]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_matching.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.matching'`

- [ ] **Step 3: Write `app/matching.py`**

```python
from __future__ import annotations

import re
import unicodedata

from app.dates import strip_date_prefix


def normalize(title: str) -> str:
    """Strip any date prefix, remove diacritics, lowercase, collapse whitespace.

    Note: equality is what matters, and both sides are normalized the same way, so
    letters that NFKD does not decompose (e.g. Vietnamese 'đ') stay consistent on
    both sides and still compare equal.
    """
    without_date = strip_date_prefix(title)
    decomposed = unicodedata.normalize("NFKD", without_date)
    no_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_marks).strip().lower()


def matches_any(title: str, base_titles: list[str]) -> bool:
    norm = normalize(title)
    return any(norm == normalize(b) for b in base_titles)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_matching.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/matching.py tests/test_matching.py
git commit -m "feat: title normalization and fuzzy matching"
```

---

## Task 3: `app/config.py` — env loading & validation

**Files:**
- Create: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
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
    assert cfg.schedule_day == "sun"
    assert cfg.schedule_hour == 18
    assert cfg.recent_window_days == 7
    assert cfg.dry_run is False


def test_load_config_dry_run_true(monkeypatch):
    _set(monkeypatch, DRY_RUN="true")
    assert load_config().dry_run is True


def test_load_config_missing_required_raises(monkeypatch):
    _set(monkeypatch)
    monkeypatch.delenv("YOUTUBE_CLIENT_ID")
    with pytest.raises(ValueError, match="YOUTUBE_CLIENT_ID"):
        load_config()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Write `app/config.py`**

```python
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
    schedule_day: str
    schedule_hour: int
    recent_window_days: int
    dry_run: bool
    log_level: str


def _require(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise ValueError(f"Missing required env var: {name}")
    return val


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
        schedule_day=os.getenv("SCHEDULE_DAY", "sun").strip(),
        schedule_hour=int(os.getenv("SCHEDULE_HOUR", "18")),
        recent_window_days=int(os.getenv("RECENT_WINDOW_DAYS", "7")),
        dry_run=os.getenv("DRY_RUN", "false").strip().lower() in ("1", "true", "yes"),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed)

Note: `load_dotenv()` is a no-op when no `.env` file exists, so monkeypatched env vars win in tests.

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: env config loading and validation"
```

---

## Task 4: `app/retitle.py` — pure decision logic

**Files:**
- Create: `app/retitle.py`
- Test: `tests/test_retitle.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_retitle.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_retitle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retitle'`

- [ ] **Step 3: Write `app/retitle.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.dates import format_date_prefix, has_date_prefix, parse_iso_utc
from app.matching import matches_any


@dataclass(frozen=True)
class Broadcast:
    video_id: str
    title: str
    start_iso: str  # actualStartTime or scheduledStartTime, ISO-8601 UTC


@dataclass(frozen=True)
class Change:
    video_id: str
    old_title: str
    new_title: str


def decide(
    broadcasts: list[Broadcast],
    base_titles: list[str],
    tz: str,
    window_days: int | None = None,
    now_utc: datetime | None = None,
) -> list[Change]:
    """Return retitle changes for broadcasts that match a base title and lack a date.

    If window_days is set, only broadcasts whose start time is within the last
    window_days (relative to now_utc, default current UTC time) are considered.
    """
    changes: list[Change] = []
    ref = now_utc or datetime.now(timezone.utc)
    for b in broadcasts:
        if has_date_prefix(b.title):
            continue
        if not matches_any(b.title, base_titles):
            continue
        start = parse_iso_utc(b.start_iso)
        if window_days is not None and start < ref - timedelta(days=window_days):
            continue
        prefix = format_date_prefix(start, tz)
        changes.append(Change(b.video_id, b.title, prefix + b.title))
    return changes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_retitle.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add app/retitle.py tests/test_retitle.py
git commit -m "feat: pure retitle decision logic"
```

---

## Task 5: `app/state.py` — atomic JSON state

**Files:**
- Create: `app/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_state.py`:
```python
from app.state import load_state, save_state


def test_load_missing_returns_empty(tmp_path):
    assert load_state(str(tmp_path / "nope.json")) == {}


def test_save_then_load_roundtrips(tmp_path):
    p = str(tmp_path / "state.json")
    save_state({"last_run": "2026-05-10T18:00:00Z", "changed": 3}, p)
    assert load_state(p) == {"last_run": "2026-05-10T18:00:00Z", "changed": 3}


def test_load_corrupt_returns_empty(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{not valid json")
    assert load_state(str(p)) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.state'`

- [ ] **Step 3: Write `app/state.py`**

```python
from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_PATH = "state.json"


def load_state(path: str = DEFAULT_PATH) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, Any], path: str = DEFAULT_PATH) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/state.py tests/test_state.py
git commit -m "feat: atomic JSON state persistence"
```

---

## Task 6: `app/youtube.py` — YouTube Data API wrapper

**Files:**
- Create: `app/youtube.py`
- Test: `tests/test_youtube.py`

- [ ] **Step 1: Write the failing tests** (using a fake service object — no network)

`tests/test_youtube.py`:
```python
from unittest.mock import MagicMock

from app.youtube import list_broadcasts, get_video_snippet, update_title


def _make_service(pages):
    """pages: list of response dicts returned by successive execute() calls."""
    service = MagicMock()
    execute = service.liveBroadcasts.return_value.list.return_value.execute
    execute.side_effect = pages
    return service


def test_list_broadcasts_paginates_and_extracts():
    pages = [
        {
            "items": [
                {
                    "id": "v1",
                    "snippet": {
                        "title": "A",
                        "actualStartTime": "2026-05-10T18:00:00Z",
                    },
                }
            ],
            "nextPageToken": "p2",
        },
        {
            "items": [
                {
                    "id": "v2",
                    "snippet": {
                        "title": "B",
                        "scheduledStartTime": "2026-05-17T18:00:00Z",
                    },
                }
            ]
        },
    ]
    service = _make_service(pages)
    result = list_broadcasts(service, ["all"])
    assert result == [
        ("v1", "A", "2026-05-10T18:00:00Z"),
        ("v2", "B", "2026-05-17T18:00:00Z"),
    ]


def test_list_broadcasts_skips_items_without_start():
    pages = [{"items": [{"id": "v1", "snippet": {"title": "A"}}]}]
    service = _make_service(pages)
    assert list_broadcasts(service, ["all"]) == []


def test_get_video_snippet_returns_snippet():
    service = MagicMock()
    service.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"title": "A", "categoryId": "22"}}]
    }
    assert get_video_snippet(service, "v1") == {"title": "A", "categoryId": "22"}


def test_update_title_sets_title_and_preserves_snippet():
    service = MagicMock()
    update = service.videos.return_value.update
    update_title(service, "v1", {"title": "Old", "categoryId": "22"}, "New")
    _, kwargs = update.call_args
    assert kwargs["part"] == "snippet"
    assert kwargs["body"] == {
        "id": "v1",
        "snippet": {"title": "New", "categoryId": "22"},
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_youtube.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.youtube'`

- [ ] **Step 3: Write `app/youtube.py`**

```python
from __future__ import annotations

import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
_NUM_RETRIES = 3  # googleapiclient applies exponential backoff for 5xx/429


def build_service(client_id: str, client_secret: str, refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def list_broadcasts(service, statuses):
    """Return [(video_id, title, start_iso)] for the given broadcastStatus values.

    statuses: iterable from {'all','active','upcoming','completed'}.
    Uses liveBroadcasts.list, which returns only livestreams (never plain uploads).
    start_iso prefers actualStartTime, falling back to scheduledStartTime; items
    with neither are skipped.
    """
    results = []
    seen = set()
    for status in statuses:
        page_token = None
        while True:
            resp = (
                service.liveBroadcasts()
                .list(
                    part="snippet,status",
                    broadcastStatus=status,
                    broadcastType="all",
                    maxResults=50,
                    pageToken=page_token,
                )
                .execute(num_retries=_NUM_RETRIES)
            )
            for item in resp.get("items", []):
                vid = item["id"]
                if vid in seen:
                    continue
                snip = item.get("snippet", {})
                start = snip.get("actualStartTime") or snip.get("scheduledStartTime")
                if not start:
                    continue
                seen.add(vid)
                results.append((vid, snip.get("title", ""), start))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return results


def get_video_snippet(service, video_id: str):
    resp = (
        service.videos()
        .list(part="snippet", id=video_id)
        .execute(num_retries=_NUM_RETRIES)
    )
    items = resp.get("items", [])
    return items[0]["snippet"] if items else None


def update_title(service, video_id: str, snippet: dict, new_title: str):
    new_snippet = dict(snippet)
    new_snippet["title"] = new_title
    body = {"id": video_id, "snippet": new_snippet}
    return (
        service.videos()
        .update(part="snippet", body=body)
        .execute(num_retries=_NUM_RETRIES)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_youtube.py -v`
Expected: PASS (4 passed)

Note: `MagicMock().execute(num_retries=3)` ignores kwargs, so the `side_effect`/`return_value` still drive the test responses.

- [ ] **Step 5: Commit**

```bash
git add app/youtube.py tests/test_youtube.py
git commit -m "feat: YouTube Data API wrapper for broadcasts and titles"
```

---

## Task 7: `app/telegram.py` — Telegram client

**Files:**
- Create: `app/telegram.py`
- Test: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing tests** (patch `requests` inside the module)

`tests/test_telegram.py`:
```python
from unittest.mock import MagicMock, patch

from app.telegram import send_message, get_updates


@patch("app.telegram.requests")
def test_send_message_posts_json(mock_requests):
    resp = MagicMock()
    resp.json.return_value = {"ok": True}
    mock_requests.post.return_value = resp
    out = send_message("TOKEN", "123", "hello")
    assert out == {"ok": True}
    args, kwargs = mock_requests.post.call_args
    assert "botTOKEN/sendMessage" in args[0]
    assert kwargs["json"] == {"chat_id": "123", "text": "hello"}


@patch("app.telegram.requests")
def test_get_updates_returns_result_list(mock_requests):
    resp = MagicMock()
    resp.json.return_value = {"ok": True, "result": [{"update_id": 5}]}
    mock_requests.get.return_value = resp
    out = get_updates("TOKEN", offset=4)
    assert out == [{"update_id": 5}]
    args, kwargs = mock_requests.get.call_args
    assert kwargs["params"]["offset"] == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.telegram'`

- [ ] **Step 3: Write `app/telegram.py`**

```python
from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)
_API = "https://api.telegram.org/bot{token}/{method}"


def send_message(token: str, chat_id: str, text: str) -> dict:
    url = _API.format(token=token, method="sendMessage")
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_updates(token: str, offset: int | None = None, timeout: int = 30) -> list:
    url = _API.format(token=token, method="getUpdates")
    params: dict = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(url, params=params, timeout=timeout + 10)
    resp.raise_for_status()
    return resp.json().get("result", [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_telegram.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/telegram.py tests/test_telegram.py
git commit -m "feat: Telegram send and long-poll client"
```

---

## Task 8: `app/jobs.py` — job orchestration

**Files:**
- Create: `app/jobs.py`
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests** (monkeypatch the `youtube` module functions)

`tests/test_jobs.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.jobs'`

- [ ] **Step 3: Write `app/jobs.py`**

```python
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app import youtube
from app.retitle import Broadcast, decide

log = logging.getLogger(__name__)


@dataclass
class JobReport:
    scanned: int = 0
    changed: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)
    changes: list[tuple[str, str]] = field(default_factory=list)  # (video_id, new_title)
    dry_run: bool = False


def run_job(service, config, statuses, window_days) -> JobReport:
    raw = youtube.list_broadcasts(service, statuses)
    broadcasts = [Broadcast(vid, title, start) for vid, title, start in raw]
    changes = decide(broadcasts, config.base_titles, config.timezone, window_days)
    report = JobReport(
        scanned=len(broadcasts),
        skipped=len(broadcasts) - len(changes),
        dry_run=config.dry_run,
    )
    for ch in changes:
        try:
            if config.dry_run:
                log.info("[DRY_RUN] would retitle %s -> %s", ch.video_id, ch.new_title)
            else:
                snippet = youtube.get_video_snippet(service, ch.video_id)
                if snippet is None:
                    raise RuntimeError("video not found")
                youtube.update_title(service, ch.video_id, snippet, ch.new_title)
                log.info("retitled %s -> %s", ch.video_id, ch.new_title)
            report.changed += 1
            report.changes.append((ch.video_id, ch.new_title))
        except Exception as e:  # noqa: BLE001 - one failure must not abort the batch
            log.exception("failed to retitle %s", ch.video_id)
            report.failures.append(f"{ch.video_id}: {e}")
    return report


def weekly_job(service, config) -> JobReport:
    return run_job(service, config, statuses=["all"], window_days=config.recent_window_days)


def backdate_all(service, config) -> JobReport:
    return run_job(service, config, statuses=["completed"], window_days=None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_jobs.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/jobs.py tests/test_jobs.py
git commit -m "feat: weekly and backdate job orchestration"
```

---

## Task 9: `app/notify.py` — Telegram message formatting

**Files:**
- Create: `app/notify.py`
- Test: `tests/test_notify.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_notify.py`:
```python
from app.jobs import JobReport
from app.notify import format_report, format_status


def test_format_report_summary_and_changes():
    r = JobReport(scanned=5, changed=2, skipped=3, dry_run=False)
    r.changes = [("v1", "Sunday, May 10th, 2026 - Worship Service")]
    text = format_report("Weekly run", r)
    assert "Weekly run" in text
    assert "Scanned: 5" in text
    assert "Changed: 2" in text
    assert "Sunday, May 10th, 2026 - Worship Service" in text


def test_format_report_marks_dry_run_and_failures():
    r = JobReport(scanned=1, changed=0, skipped=1, dry_run=True)
    r.failures = ["v9: boom"]
    text = format_report("Backdate", r)
    assert "DRY_RUN" in text
    assert "v9: boom" in text


def test_format_status_includes_fields():
    state = {
        "last_run_at": "2026-05-10T18:00:05Z",
        "last_result": "changed 1, failures 0",
        "last_error": None,
    }
    text = format_status(state, next_run="2026-05-17 18:00 PDT", started_at="2026-05-10T00:00:00Z")
    assert "2026-05-10T18:00:05Z" in text
    assert "2026-05-17 18:00 PDT" in text
    assert "changed 1" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.notify'`

- [ ] **Step 3: Write `app/notify.py`**

```python
from __future__ import annotations

from app.jobs import JobReport

_MAX_LISTED = 25


def format_report(title: str, report: JobReport) -> str:
    lines = [
        title,
        f"Scanned: {report.scanned}",
        f"Changed: {report.changed}",
        f"Skipped: {report.skipped}",
    ]
    if report.dry_run:
        lines.append("(DRY_RUN — no changes written)")
    for _vid, new in report.changes[:_MAX_LISTED]:
        lines.append(f"• {new}")
    extra = len(report.changes) - _MAX_LISTED
    if extra > 0:
        lines.append(f"…and {extra} more")
    if report.failures:
        lines.append(f"Failures ({len(report.failures)}):")
        lines.extend(f"⚠ {f}" for f in report.failures[:10])
    return "\n".join(lines)


def format_status(state: dict, next_run: str, started_at: str) -> str:
    return "\n".join(
        [
            "Status: running",
            f"Started: {started_at}",
            f"Next run: {next_run}",
            f"Last run: {state.get('last_run_at', 'never')}",
            f"Last result: {state.get('last_result', 'n/a')}",
            f"Last error: {state.get('last_error') or 'none'}",
        ]
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_notify.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/notify.py tests/test_notify.py
git commit -m "feat: Telegram report and status formatting"
```

---

## Task 10: `app/main.py` — daemon (scheduler + command loop)

**Files:**
- Create: `app/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests** for the pure helper `handle_command`

`tests/test_main.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write `app/main.py`**

```python
from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import state as state_mod
from app import telegram, youtube
from app.config import Config, load_config
from app.jobs import JobReport, backdate_all, weekly_job
from app.notify import format_report, format_status

log = logging.getLogger("yt-retitle")

HELP_TEXT = (
    "Commands:\n"
    "/status — last run, next run, errors\n"
    "/run — run the weekly job now\n"
    "/backdate — retitle all past livestreams (idempotent)\n"
    "/help — this message"
)


@dataclass
class Context:
    config: Config
    service: object
    scheduler: object
    started_at: str
    send: Callable[[str], None]
    next_run: Callable[[], str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _record(report: JobReport) -> None:
    state = state_mod.load_state()
    state["last_run_at"] = _now_iso()
    state["last_result"] = f"changed {report.changed}, failures {len(report.failures)}"
    state["last_error"] = report.failures[0] if report.failures else None
    state_mod.save_state(state)


def _run_and_report(ctx: Context, title: str, fn) -> None:
    try:
        report = fn(ctx.service, ctx.config)
        _record(report)
        ctx.send(format_report(title, report))
    except Exception as e:  # noqa: BLE001 - never let a job crash the daemon
        log.exception("%s failed", title)
        state = state_mod.load_state()
        state["last_error"] = f"{title}: {e}"
        state_mod.save_state(state)
        ctx.send(f"⚠ {title} failed: {e}")


def handle_command(ctx: Context, chat_id: str, text: str) -> None:
    if str(chat_id) != str(ctx.config.telegram_chat_id):
        log.warning("ignoring command from unauthorized chat %s", chat_id)
        return
    cmd = text.strip().split()[0].lower() if text.strip() else ""
    if cmd == "/status":
        ctx.send(format_status(state_mod.load_state(), ctx.next_run(), ctx.started_at))
    elif cmd == "/help":
        ctx.send(HELP_TEXT)
    elif cmd == "/run":
        ctx.send("Running weekly job…")
        _run_and_report(ctx, "Weekly run (manual)", weekly_job)
    elif cmd == "/backdate":
        ctx.send("Starting backdate of all past livestreams…")
        _run_and_report(ctx, "Backdate", backdate_all)
    else:
        ctx.send(f"Unknown command: {cmd}\n\n{HELP_TEXT}")


def _scheduled_weekly(ctx: Context) -> None:
    _run_and_report(ctx, "Weekly run", weekly_job)


def main() -> None:
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    service = youtube.build_service(
        config.youtube_client_id,
        config.youtube_client_secret,
        config.youtube_refresh_token,
    )

    scheduler = BackgroundScheduler(timezone=config.timezone)

    def next_run() -> str:
        jobs = scheduler.get_jobs()
        if jobs and jobs[0].next_run_time:
            return jobs[0].next_run_time.strftime("%Y-%m-%d %H:%M %Z")
        return "unscheduled"

    def send(text: str) -> None:
        try:
            telegram.send_message(config.telegram_bot_token, config.telegram_chat_id, text)
        except Exception:  # noqa: BLE001
            log.exception("failed to send Telegram message")

    ctx = Context(
        config=config,
        service=service,
        scheduler=scheduler,
        started_at=_now_iso(),
        send=send,
        next_run=next_run,
    )

    scheduler.add_job(
        lambda: _scheduled_weekly(ctx),
        CronTrigger(
            day_of_week=config.schedule_day,
            hour=config.schedule_hour,
            minute=0,
            timezone=ZoneInfo(config.timezone),
        ),
        id="weekly",
    )
    scheduler.start()
    send(f"✅ yt-retitle started. Next weekly run: {next_run()}"
         + (" (DRY_RUN)" if config.dry_run else ""))

    offset = None
    log.info("entering Telegram poll loop")
    while True:
        try:
            updates = telegram.get_updates(config.telegram_bot_token, offset=offset, timeout=30)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                if text:
                    handle_command(ctx, chat_id, text)
        except Exception:  # noqa: BLE001 - keep polling through transient errors
            log.exception("poll loop error; backing off 10s")
            time.sleep(10)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YouTube livestream auto-retitle")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["serve", "backdate", "weekly"],
        default="serve",
        help="serve (default daemon), backdate (one-shot), weekly (one-shot)",
    )
    args = parser.parse_args()

    if args.command == "serve":
        main()
    else:
        cfg = load_config()
        logging.basicConfig(level=getattr(logging, cfg.log_level, logging.INFO), stream=sys.stdout)
        svc = youtube.build_service(
            cfg.youtube_client_id, cfg.youtube_client_secret, cfg.youtube_refresh_token
        )
        fn = backdate_all if args.command == "backdate" else weekly_job
        rep = fn(svc, cfg)
        print(format_report(args.command, rep))
        try:
            telegram.send_message(
                cfg.telegram_bot_token, cfg.telegram_chat_id, format_report(args.command, rep)
            )
        except Exception:  # noqa: BLE001
            log.exception("failed to send Telegram report")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: daemon with scheduler, Telegram command loop, and CLI"
```

---

## Task 11: `get_token.py` — OAuth bootstrap helper

**Files:**
- Create: `get_token.py`

- [ ] **Step 1: Write `get_token.py`** (run manually; no unit test — it opens a browser)

```python
"""One-time helper: mint a YouTube OAuth refresh token.

Run on a machine with a browser:
    YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... python get_token.py

Copy the printed YOUTUBE_REFRESH_TOKEN line into your .env.
"""
from __future__ import annotations

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def main() -> None:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in the environment first.")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        sys.exit("No refresh token returned. Re-run; ensure prompt=consent and offline access.")
    print("\n# Add this line to your .env:")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-check it imports**

Run: `.venv/bin/python -c "import ast; ast.parse(open('get_token.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add get_token.py
git commit -m "feat: OAuth refresh-token bootstrap helper"
```

---

## Task 12: Deploy assets & docs

**Files:**
- Create: `deploy/yt-retitle.service`
- Create: `.env.example`
- Create: `docs/SETUP.md`
- Create: `CLAUDE.md`

- [ ] **Step 1: Create `deploy/yt-retitle.service`**

```ini
[Unit]
Description=YouTube Livestream Auto-Retitle Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/yt-retitle
ExecStart=/opt/yt-retitle/.venv/bin/python -m app.main serve
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Note: the app uses `python-dotenv`, which loads `.env` from `WorkingDirectory`, so no `EnvironmentFile` is needed (this also avoids systemd quoting issues with the Vietnamese title).

- [ ] **Step 2: Create `.env.example`**

```text
# --- YouTube OAuth (see docs/SETUP.md) ---
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=

# --- Telegram ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# --- Behavior ---
# Multiple titles separated by ||
BASE_TITLES=Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển
TIMEZONE=America/Los_Angeles
SCHEDULE_DAY=sun
SCHEDULE_HOUR=18
RECENT_WINDOW_DAYS=7
# Set true to preview without writing changes
DRY_RUN=true
LOG_LEVEL=INFO
```

- [ ] **Step 3: Create `docs/SETUP.md`**

````markdown
# Setup Guide

## 1. Google Cloud OAuth (one time)

1. Go to <https://console.cloud.google.com/> → create a project (e.g. `yt-retitle`).
2. **APIs & Services → Library →** enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen:**
   - User type: **External**.
   - Fill app name + your email.
   - **Publishing status → PUBLISH APP → confirm "In production".**
     > ⚠️ If you leave it in *Testing*, refresh tokens expire after **7 days** and the
     > service stops working every week. Production tokens do not expire.
   - Add scope `.../auth/youtube.force-ssl` (optional to list; the script requests it).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID:**
   - Application type: **Desktop app**.
   - Download / copy the **Client ID** and **Client secret**.

## 2. Mint the refresh token (run on your laptop, with a browser)

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
YOUTUBE_CLIENT_ID=xxx YOUTUBE_CLIENT_SECRET=yyy python get_token.py
```

A browser opens — log in **with the Google account that owns the YouTube channel** and
approve. The script prints:

```
YOUTUBE_REFRESH_TOKEN=1//0g...
```

Copy that value.

## 3. Telegram

- Your bot token comes from @BotFather (you already have a bot).
- Get your chat ID: message the bot, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
- Put both in `.env` as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

## 4. VPS install

```bash
sudo mkdir -p /opt/yt-retitle && sudo chown $USER /opt/yt-retitle
git clone <your-repo> /opt/yt-retitle && cd /opt/yt-retitle
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env && nano .env          # fill in all values; keep DRY_RUN=true first
```

### Preview before writing anything

```bash
.venv/bin/python -m app.main backdate       # DRY_RUN=true → logs what it WOULD change
```

When the preview looks right, set `DRY_RUN=false` in `.env` and run the real backdate:

```bash
.venv/bin/python -m app.main backdate
```

### Install the service (weekly automation + Telegram control)

```bash
sudo cp deploy/yt-retitle.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yt-retitle
sudo systemctl status yt-retitle
journalctl -u yt-retitle -f
```

## 5. Health check

In Telegram, send the bot:

- `/status` — last run, next run, last error
- `/run` — run the weekly job now
- `/backdate` — retitle all past livestreams
- `/help`

On startup the service messages you `✅ yt-retitle started. Next weekly run: …`.
````

- [ ] **Step 4: Create `CLAUDE.md`**

````markdown
# yt-livestream-retitle-script

Python daemon that prepends each YouTube **livestream's** own broadcast date (Pacific
time) to its title — once for the backlog, then automatically every Sunday 18:00 Pacific.
Controlled and monitored via Telegram. Only livestreams are touched (never plain uploads),
because broadcast IDs come from `liveBroadcasts.list`.

## Full setup

See **[docs/SETUP.md](docs/SETUP.md)** for Google Cloud OAuth, the refresh-token bootstrap,
Telegram wiring, and VPS/systemd install.

## Updating `.env` on the VPS

The app reads `/opt/yt-retitle/.env` (via python-dotenv) at start. To change config:

```bash
nano /opt/yt-retitle/.env
sudo systemctl restart yt-retitle
```

### `.env` reference

| Var | Meaning |
|---|---|
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | OAuth Desktop client (Google Cloud) |
| `YOUTUBE_REFRESH_TOKEN` | From `get_token.py`; needs the consent screen in **Production** or it expires in 7 days |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Your existing bot + your chat id |
| `BASE_TITLES` | Title(s) to match, `||`-separated. Diacritics/case/whitespace-insensitive |
| `TIMEZONE` | Default `America/Los_Angeles` (auto PST/PDT) |
| `SCHEDULE_DAY` / `SCHEDULE_HOUR` | Default `sun` / `18` |
| `RECENT_WINDOW_DAYS` | Weekly scan window, default `7` |
| `DRY_RUN` | `true` = preview only (no writes). Start here. |
| `LOG_LEVEL` | `INFO` default |

## Commands

| | |
|---|---|
| Daemon | `python -m app.main serve` (systemd runs this) |
| One-shot backdate | `python -m app.main backdate` |
| One-shot weekly | `python -m app.main weekly` |
| Tests | `python -m pytest` |
| Telegram | `/status`, `/run`, `/backdate`, `/help` |

## How it decides what to retitle

1. List livestream broadcasts via `liveBroadcasts.list` (never plain uploads).
2. Skip any title that already starts with a date prefix (idempotent).
3. Match remaining titles against `BASE_TITLES` (diacritic/case/whitespace-insensitive).
4. Prepend that stream's own date — `actualStartTime` (fallback `scheduledStartTime`),
   converted **UTC → Pacific** — as `Weekday, Month Dayth, Year - `.

Weekly run looks back `RECENT_WINDOW_DAYS`; backdate scans all completed broadcasts.

## Architecture

Pure logic (`dates`, `matching`, `retitle`, `notify`) is unit-tested and network-free.
`youtube`/`telegram` are thin wrappers. `jobs` orchestrates; `main` runs the scheduler +
Telegram loop. See `docs/superpowers/specs/` and `docs/superpowers/plans/` for design.
````

- [ ] **Step 5: Verify the systemd unit and env example are well-formed**

Run: `test -f deploy/yt-retitle.service && test -f .env.example && test -f docs/SETUP.md && test -f CLAUDE.md && echo ok`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add deploy/yt-retitle.service .env.example docs/SETUP.md CLAUDE.md
git commit -m "docs: setup guide, systemd unit, env example, CLAUDE.md"
```

---

## Task 13: Final verification

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: ALL PASS (dates 6, matching 6, config 4, retitle 5, state 3, youtube 4, telegram 2, jobs 4, notify 3, main 4 = 41 tests).

- [ ] **Step 2: Confirm the daemon module imports cleanly**

Run: `.venv/bin/python -c "import app.main; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: Confirm `.env` is gitignored and not committed**

Run: `git check-ignore .env || echo "WARNING: .env not ignored"; git ls-files | grep -c '\.env$' | grep -q '^0$' && echo "ok: .env not tracked"`
Expected: prints `.env` (ignored) and `ok: .env not tracked`

- [ ] **Step 4: Final commit if anything outstanding**

```bash
git status
```
Expected: clean tree (or commit any stragglers).

---

## Self-Review Notes

- **Spec coverage:** backdate (Task 8/10), weekly Sunday-18:00-Pacific (Task 10 CronTrigger), Pacific conversion (Task 1), match configured titles fuzzy (Task 2/4), recent-window self-heal (Task 4/8), livestreams-only via `liveBroadcasts.list` (Task 6), Telegram notify + `/status` health + `/backdate`/`/run` (Task 9/10), error handling + retries + DRY_RUN (Task 6/8/10), VPS systemd + OAuth Production gotcha + docs/SETUP.md + CLAUDE.md env instructions (Task 11/12). ✅
- **Type consistency:** `Broadcast(video_id,title,start_iso)`, `Change(video_id,old_title,new_title)`, `JobReport`, `Context`, and `decide(...)`/`run_job(...)`/`weekly_job`/`backdate_all` signatures are consistent across tasks.
- **No placeholders:** every code/test step is complete and runnable.
