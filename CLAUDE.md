# yt-livestream-retitle-script

Prepends each YouTube **livestream's** own broadcast date (Pacific time) to its title — once
for the backlog, then automatically every week. Runs on **GitHub Actions** (no server);
posts a report to Telegram after each run. Only livestreams are touched (never plain uploads),
because IDs come from `liveBroadcasts.list` and the uploads playlist filtered by
`liveStreamingDetails`.

## Full setup

See **[docs/SETUP.md](docs/SETUP.md)** for Google Cloud OAuth, the refresh-token bootstrap,
Telegram wiring, and the GitHub Actions secrets.

## Deployment

Runs on GitHub Actions — `.github/workflows/retitle.yml`:

- **Schedule:** `cron: "0 2 * * 1"` (Mondays 02:00 UTC ≈ Sunday evening Pacific).
- **Manual:** Actions tab → Run workflow → `command` (weekly/backdate) + `dry_run` toggle.
- **Config** lives in repo **secrets** (Settings → Secrets and variables → Actions), not `.env`.
- `keepalive.yml` makes a monthly commit so GitHub doesn't auto-pause the schedule.

### Secrets reference

| Secret | Meaning |
|---|---|
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | OAuth Desktop client (Google Cloud) |
| `YOUTUBE_REFRESH_TOKEN` | From `get_token.py`; needs the consent screen in **Production** or it expires in 7 days |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Bot token + your chat id |
| `BASE_TITLES` | Title(s) to match, `||`-separated. Diacritics/case/whitespace-insensitive |

`TIMEZONE` is hardcoded to `America/Los_Angeles` in the workflow. `RECENT_WINDOW_DAYS` (default
7), `MIN_WORSHIP_MINUTES` (default 60), and `DRY_RUN` can be set as env in the workflow if needed.

## Commands (CLI; the workflow calls these)

| | |
|---|---|
| Backdate full history | `python -m app.main backdate` |
| Weekly (recent window) | `python -m app.main weekly` |
| Diagnostic list | `python -m app.main list` (print livestreams each source returns; no changes) |
| Review unmatched | `python -m app.main review` (read-only: unmatched livestreams → stdout + `review_candidates.csv`) |
| Tests | `python -m pytest` |
| Lint | `make lint` (ruff) |

Each `backdate`/`weekly` run prints its report and sends it to Telegram. `review` is
read-only — it lists the livestreams that are neither dated nor on the allowlist,
printing them to the Actions log and writing `review_candidates.csv` (uploaded as a
workflow artifact). Each row carries `weekday` and `duration_min` columns so you can
filter out non-Sunday streams and sanity-check the ≥`MIN_WORSHIP_MINUTES` cutoff. Output
path overridable via `REVIEW_OUTPUT_FILE`.

## How it decides what to retitle

1. List livestreams via `liveBroadcasts.list` unioned with the uploads playlist (filtered to
   videos with `liveStreamingDetails`), deduped by video id — never plain uploads.
2. Skip any title that already starts with a date prefix (idempotent).
3. A stream **qualifies** if its title is on the `BASE_TITLES` allowlist
   (diacritic/case/whitespace-insensitive) **OR** its video runs at least
   `MIN_WORSHIP_MINUTES` (default 60) — a full worship service, however it was titled.
4. Each qualifying stream is normalised to **`<date> - <canonical>`**: its own broadcast
   date (`actualStartTime`, fallback `scheduledStartTime`, **UTC → Pacific**, as
   `Weekday, Month Dayth, Year - `) plus the **canonical** title (the first `BASE_TITLES`
   entry). This **overwrites** whatever was there — sermon text a team member pasted in, or
   an old bracketed date — so every service is titled identically and stays under YouTube's
   100-char title limit. Already-correct titles are skipped (idempotent), including ones
   that already carry a date prefix.

The duration gate is what catches mis-titled services: a 60+ minute livestream is a
service even if its title was replaced with a sermon passage. Short streams (sermon clips,
test streams, `choir`) never qualify and are left untouched. Duration comes from
`videos.list contentDetails.duration`, fetched in one batched call per run; a stream still
processing reports no length and is skipped that run (caught the next). Use `review`
(read-only, with a duration column) to eyeball the cutoff before a real run.

> **Title length:** YouTube rejects titles over 100 chars (`invalidTitle`). `<date> -
> <canonical>` is well under it; `decide()` also defensively skips any target over
> `MAX_TITLE_LEN` (100) so a run never fails on length.

Weekly run looks back `RECENT_WINDOW_DAYS`; backdate scans all history. Run a
`backdate` with `DRY_RUN=true` first to preview before writing. (A full backdate updates
~200 titles, which can exceed the YouTube daily API quota; it's idempotent, so just re-run
the next day to finish.)

## Architecture

Pure logic (`dates`, `matching`, `retitle`, `notify`) is unit-tested and network-free.
`youtube`/`telegram` are thin wrappers. `jobs` orchestrates; `main` is the CLI entrypoint the
workflow invokes. See `docs/superpowers/specs/` and `docs/superpowers/plans/` for design.
