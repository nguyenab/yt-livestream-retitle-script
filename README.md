# yt-livestream-retitle-script

Prepends each YouTube **livestream's** own broadcast date (Pacific time) to its title — once
for the whole backlog, then automatically every Sunday 18:00 Pacific. Built for a channel whose
streams are pushed by Streamlabs with a fixed title and no date token.

```
Lễ thờ phượng - Worship Service …   →   Sunday, May 10th, 2026 - Lễ thờ phượng - Worship Service …
```

Controlled and monitored entirely through an existing Telegram bot. Only livestreams are ever
touched — never plain uploads.

## Features

- **One-time backdate** of every past livestream, each with its own broadcast date.
- **Weekly auto-retitle** (Sun 18:00 `America/Los_Angeles`, auto PST/PDT), self-healing over a
  configurable recent window.
- **Telegram control:** `/status`, `/run`, `/backdate`, `/help`; startup ping with the next run.
- **Livestreams-only** via `liveBroadcasts.list` **and** an uploads-playlist +
  `liveStreamingDetails` fallback (deduped), so streams a persistent stream key hides from
  `liveBroadcasts` are still caught.
- **Robust:** UTC→Pacific date conversion, idempotent (never double-prefixes), per-video error
  isolation, API retry/backoff, `DRY_RUN` preview, 409-conflict alerting, and a resident daemon
  that survives transient failures.

## Quickstart

Full instructions — Google Cloud OAuth (publish the consent screen to **Production** or tokens
expire in 7 days), the refresh-token bootstrap, Telegram wiring, and VPS/systemd install — are
in **[docs/SETUP.md](docs/SETUP.md)**.

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env && nano .env          # fill values; keep DRY_RUN=true first
python -m app.main list                    # verify your streams are visible (no changes)
python -m app.main backdate                # DRY_RUN=true → preview; flip to false for real
```

## Commands

| Command | What it does |
|---|---|
| `python -m app.main serve` | Run the daemon (scheduler + Telegram loop); systemd runs this |
| `python -m app.main backdate` | Retitle all past livestreams (idempotent) |
| `python -m app.main weekly` | Run the weekly job once |
| `python -m app.main list` | Diagnostic: print livestreams each source returns; no changes |
| `python -m pytest` | Run the test suite |

Telegram: `/status`, `/run`, `/backdate`, `/help`.

## How it works

1. List livestreams via `liveBroadcasts.list` unioned with the uploads playlist (filtered to
   videos with `liveStreamingDetails`), deduped by video id.
2. Skip any title already starting with a date prefix (idempotent).
3. Match the rest against `BASE_TITLES` (diacritic/case/whitespace-insensitive).
4. Prepend that stream's own date — `actualStartTime` (fallback `scheduledStartTime`), converted
   UTC→Pacific — as `Weekday, Month Dayth, Year - `.

The weekly run looks back `RECENT_WINDOW_DAYS`; backdate scans full history.

## Configuration & architecture

`.env` reference and VPS update steps live in **[CLAUDE.md](CLAUDE.md)**. Pure logic (`dates`,
`matching`, `retitle`, `notify`) is network-free and unit-tested; `youtube`/`telegram` are thin
wrappers; `jobs` orchestrates and `main` runs the scheduler + Telegram loop. Design docs are in
`docs/superpowers/`.
