# yt-livestream-retitle-script

Prepends each YouTube **livestream's** own broadcast date (Pacific time) to its title — once
for the whole backlog, then automatically every week. Built for a channel whose streams are
pushed by Streamlabs with a fixed title and no date token.

```
Lễ thờ phượng - Worship Service …   →   Sunday, May 10th, 2026 - Lễ thờ phượng - Worship Service …
```

Runs entirely on **GitHub Actions** — no server to maintain — and posts a report to Telegram
after each run. Only livestreams are ever touched, never plain uploads.

## Features

- **One-time backdate** of every past livestream, each with its own broadcast date.
- **Weekly auto-retitle** (Mondays 02:00 UTC ≈ Sunday evening `America/Los_Angeles`),
  self-healing over a configurable recent window.
- **Telegram report** after every run, plus a failure alert if something breaks.
- **Livestreams-only** via `liveBroadcasts.list` **and** an uploads-playlist +
  `liveStreamingDetails` fallback (deduped), so streams a persistent stream key hides from
  `liveBroadcasts` are still caught.
- **Robust:** UTC→Pacific date conversion, idempotent (never double-prefixes), per-video error
  isolation, API retry/backoff, and a `dry_run` preview mode.

## Deployment

Set six repo secrets and the scheduled workflow does the rest — full walkthrough (Google Cloud
OAuth → **publish the consent screen to Production** or tokens expire in 7 days, the
refresh-token bootstrap, Telegram, and the secrets) is in **[docs/SETUP.md](docs/SETUP.md)**.

- `.github/workflows/retitle.yml` — weekly schedule + manual **Run workflow** (choose
  `weekly`/`backdate`, toggle `dry_run`).
- `.github/workflows/keepalive.yml` — monthly no-op commit so GitHub doesn't auto-pause the
  schedule after 60 days of inactivity.

## Commands (CLI — the workflow calls these; also runnable locally)

| Command | What it does |
|---|---|
| `python -m app.main backdate` | Retitle all past livestreams (idempotent) |
| `python -m app.main weekly` | Run the weekly job once (recent window) |
| `python -m app.main list` | Diagnostic: print livestreams each source returns; no changes |
| `python -m pytest` | Run the test suite |
| `make lint` | Lint with ruff |

Each `backdate`/`weekly` run prints its report and sends it to Telegram. For local runs, copy
`.env.example` to `.env` and fill it in.

## How it works

1. List livestreams via `liveBroadcasts.list` unioned with the uploads playlist (filtered to
   videos with `liveStreamingDetails`), deduped by video id.
2. Skip any title already starting with a date prefix (idempotent).
3. Match the rest against `BASE_TITLES` (diacritic/case/whitespace-insensitive).
4. Prepend that stream's own date — `actualStartTime` (fallback `scheduledStartTime`), converted
   UTC→Pacific — as `Weekday, Month Dayth, Year - `.

The weekly run looks back `RECENT_WINDOW_DAYS`; backdate scans full history.

## Configuration & architecture

Secrets reference lives in **[CLAUDE.md](CLAUDE.md)**. Pure logic (`dates`, `matching`,
`retitle`, `notify`) is network-free and unit-tested; `youtube`/`telegram` are thin wrappers;
`jobs` orchestrates and `main` is the CLI entrypoint. Design docs are in `docs/superpowers/`.
