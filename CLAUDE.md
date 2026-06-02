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
