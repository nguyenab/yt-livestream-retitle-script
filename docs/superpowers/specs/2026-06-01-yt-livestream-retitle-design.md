# YouTube Livestream Auto-Retitle Service — Design

**Date:** 2026-06-01
**Status:** Approved

## Problem

A YouTube channel receives weekly livestreams pushed by Streamlabs (via multistream). The
broadcast title is static — e.g. `Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển`
— because Streamlabs cannot insert date tokens. The owner wants every livestream's title
prepended with a human-readable date, e.g.:

```
Sunday, May 10th, 2026 - Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển
```

Two needs:
1. **One-time backdate** — prepend each past livestream's own broadcast date to its title.
2. **Recurring weekly job** — every Sunday 18:00 Pacific, find outstanding (dateless) livestreams
   matching the configured title and prepend that stream's date.

This runs on a VPS, notifies an existing Telegram bot when jobs run, and exposes a Telegram
health check. It must only touch **livestreams**, never uploaded videos.

## Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Runtime | **Python 3.11+**, long-running daemon under systemd (`Restart=always`) |
| Schedule timezone | **`America/Los_Angeles`**, 18:00 (auto PST/PDT). 6 PM Pacific local. |
| Date source | Each stream's **own broadcast date** — `actualStartTime`, fallback `scheduledStartTime` — **converted from UTC to Pacific** before formatting |
| Match rule | Fuzzy match against configured base title(s): strip any existing date prefix → strip diacritics → lowercase → collapse whitespace → compare equal |
| Weekly scope | Scan upcoming + active + recently-completed broadcasts in last `RECENT_WINDOW_DAYS` (default 7); fix every matching dateless one (self-healing, idempotent) |
| Health check | Telegram bot replies to `/status`; also supports `/backdate`, `/run`, `/help` |
| YouTube write path | `videos.update` (preserves categoryId/description/tags), IDs sourced from `liveBroadcasts.list` so only livestreams are touched |

## Date format

`{Weekday}, {Month} {day}{ordinal}, {Year} - ` prepended to the existing title.

- Example: `Sunday, May 10th, 2026 - `
- Ordinal: `st/nd/rd/th` with the 11/12/13 → `th` exception.
- All formatting done after converting the UTC timestamp to `America/Los_Angeles`.

**Idempotency regex** (a title already starting with a date is skipped / stripped before match):

```
^[A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}(st|nd|rd|th), \d{4} - 
```

## Architecture

Single Python package `app/`. Small, single-purpose, independently testable modules.

| Module | Responsibility | I/O? |
|---|---|---|
| `config.py` | Load + validate `.env`; typed config object | reads env |
| `dates.py` | UTC→Pacific conversion, ordinal date formatting, date-prefix regex (detect/strip) | pure |
| `matching.py` | Normalize title, match against configured base titles | pure |
| `retitle.py` | Decision logic: given broadcasts + config → list of (video_id, old, new) changes | pure |
| `youtube.py` | OAuth client (auto-refresh), `list_broadcasts(status)`, `get_video_snippets(ids)`, `update_title(id, snippet, new_title)` | network |
| `telegram.py` | `send_message()`, `poll_updates()`; authorized to configured chat ID only | network |
| `state.py` | Read/write `state.json` (last run, next run, last result, counts, last error) | disk |
| `jobs.py` | `weekly_job()` and `backdate_all()` — orchestrate list→decide→apply→report | network |
| `main.py` | Wire APScheduler weekly trigger + Telegram command loop + startup notify | network |
| `get_token.py` | One-time OAuth installed-app flow to mint the refresh token | network |

### Data flow (weekly job)

1. `youtube.list_broadcasts()` → `liveBroadcasts.list(part=snippet,status, mine=true,
   broadcastType=all, maxResults=50)`, paginated. Returns only livestreams.
2. Filter to last `RECENT_WINDOW_DAYS` by start time.
3. `retitle.decide()` (pure) → which need retitling and the new title each.
4. For those IDs, `youtube.get_video_snippets()` → `videos.list(part=snippet)` to preserve
   `categoryId`, `description`, `tags`.
5. `youtube.update_title()` → `videos.update(part=snippet)` with modified title.
6. Build a structured report; persist to `state.json`; send Telegram summary.

`backdate_all()` is the same pipeline with `broadcastStatus=completed` and **no** window filter,
paginating the full history.

## YouTube API notes

- `liveBroadcasts.list` is the only listing used — it never returns ordinary uploads, which is how
  the "livestreams only" requirement is guaranteed.
- Title edits go through `videos.update` because a broadcast *is* a video; `snippet.title` and
  `snippet.categoryId` are required by the API, so we read the current snippet first and write it
  back with only the title changed.
- Quota: list ≈ 1 unit, `videos.list` ≈ 1 unit, `videos.update` ≈ 50 units. Weekly volume is tiny;
  backdate of N streams ≈ 51·N units — within the default 10k/day quota for normal channel sizes,
  with pagination + backoff to stay safe.

## Authentication (documented in `docs/SETUP.md`)

- No service-account path exists for YouTube channel ownership → **user OAuth**, scope
  `https://www.googleapis.com/auth/youtube.force-ssl`.
- **Critical:** if the OAuth consent screen stays in "Testing", refresh tokens expire after 7 days
  and the service silently breaks. `docs/SETUP.md` instructs publishing the consent screen to
  **"Production"** for a durable refresh token.
- `get_token.py` runs the installed-app flow once (locally or on the VPS) and outputs the refresh
  token to put in `.env`.

## Error handling & robustness

- Per-video `try/except`: one failure never aborts the batch; failures are collected and reported.
- Exponential-backoff retry on transient errors (5xx, `rateLimitExceeded`, network) — a few
  attempts, then report.
- Token-refresh failure → actionable Telegram alert (tells the user to re-auth / check Production).
- All scheduled-job exceptions caught at the top → Telegram alert; the daemon never dies.
- `DRY_RUN=true` logs intended changes without writing — first thing to run on the VPS to preview.
- Structured logging to stdout (journald) + rotating file (`logs/app.log`).
- systemd `Restart=always`; startup sends a "service up, next run: …" Telegram message.

## Telegram commands (authorized chat only)

| Command | Action |
|---|---|
| `/status` | Last run time + result, next scheduled run, uptime, last error |
| `/backdate` | Trigger one-time backfill of all completed broadcasts (idempotent) |
| `/run` | Run the weekly job immediately |
| `/help` | List commands |

## Configuration (`.env`; reference lives in CLAUDE.md)

```
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
BASE_TITLES=Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển
TIMEZONE=America/Los_Angeles
SCHEDULE_DAY=sun
SCHEDULE_HOUR=18
RECENT_WINDOW_DAYS=7
DRY_RUN=false
LOG_LEVEL=INFO
```

`BASE_TITLES` supports multiple titles separated by `||`.

## Deliverables

- `app/` package (modules above).
- `tests/` — unit tests for `dates.py`, `matching.py`, `retitle.py` (ordinals, DST-boundary dates,
  diacritic/whitespace matching, idempotent skip). Network clients mocked.
- `get_token.py` OAuth bootstrap helper.
- `requirements.txt`.
- `deploy/yt-retitle.service` systemd unit template.
- `docs/SETUP.md` — Google Cloud OAuth + Production consent + VPS systemd + Telegram setup.
- `CLAUDE.md` — `.env` reference, how to update env on the VPS, pointer to `docs/SETUP.md`.
- `.env.example`, `.gitignore` (excludes `.env`, token files, `state.json`, `logs/`).

## Testing strategy

TDD on pure logic. `dates.py`, `matching.py`, `retitle.py` are network-free and fully unit-tested.
`youtube.py` / `telegram.py` are thin wrappers behind interfaces and mocked in `jobs` tests.

## Out of scope (YAGNI)

- Editing non-livestream uploads.
- Per-stream custom titles beyond the date prefix.
- A web UI — Telegram is the entire control surface.
- Multi-channel support.
