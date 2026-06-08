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

`TIMEZONE` is hardcoded to `America/Los_Angeles` in the workflow. `RECENT_WINDOW_DAYS`
(default 7) and `DRY_RUN` can be set as env in the workflow if needed.

## Commands (CLI; the workflow calls these)

| | |
|---|---|
| Backdate full history | `python -m app.main backdate` |
| Weekly (recent window) | `python -m app.main weekly` |
| Diagnostic list | `python -m app.main list` (print livestreams each source returns; no changes) |
| Review unmatched | `python -m app.main review` (read-only: unmatched livestreams → stdout + `review_candidates.csv`) |
| Restore titles | `python -m app.main restore` (set titles verbatim from `restore_titles.csv`; one-time un-do) |
| Tests | `python -m pytest` |
| Lint | `make lint` (ruff) |

Each `backdate`/`weekly`/`restore` run prints its report and sends it to Telegram.
`review` is read-only — it lists livestreams that are neither dated nor on the allowlist,
to the Actions log and `review_candidates.csv` (uploaded as a workflow artifact). Each row
carries `weekday` and `duration_min` columns to help spot which unmatched streams are
mis-titled services worth adding to the canonicalize list. Path overridable via
`REVIEW_OUTPUT_FILE`.

## How it decides what to retitle

1. List livestreams via `liveBroadcasts.list` unioned with the uploads playlist (filtered to
   videos with `liveStreamingDetails`), deduped by video id — never plain uploads.
2. Two narrow rules — we never guess that an arbitrary title is a mistake:
   - **Allowlist match** (title on `BASE_TITLES`, diacritic/case/whitespace-insensitive):
     prepend the stream's own date (`actualStartTime`, fallback `scheduledStartTime`,
     **UTC → Pacific**, as `Weekday, Month Dayth, Year - `) and **keep the title**.
     Already-dated titles are skipped (idempotent). This is the ongoing weekly behaviour.
   - **Curated repair** (video id in **`canonicalize_ids.txt`**): a service a team member
     renamed with sermon text. Rewritten to `<date> - <canonical>` (canonical = first
     `BASE_TITLES` entry), overwriting whatever was there — including an existing date
     prefix. Idempotent. Add ids here when `review` surfaces a new mis-titled service.
3. Everything else is left untouched.

Why a curated list and not a heuristic: most non-matching livestreams are *not* mistakes
(services already titled `Worship Service [MM.DD.YYYY]`, plus special services like Good
Friday / Easter with their own correct names). Only the regular Sunday services renamed
with a sermon title are wrong, and those are enumerated explicitly in `canonicalize_ids.txt`
(path overridable via `CANONICALIZE_IDS_FILE`).

> **Title length:** YouTube rejects titles over 100 chars (`invalidTitle`). `<date> -
> <canonical>` is well under it; `decide()` defensively skips any target over
> `MAX_TITLE_LEN` (100) so a run never fails on length.

> **Restore:** `restore_titles.csv` (`video_id,title`) + the `restore` command set titles
> back verbatim — used once to undo an over-broad run. Safe to delete once applied.

Weekly run looks back `RECENT_WINDOW_DAYS`; backdate scans all history. Run with
`DRY_RUN=true` first to preview. A large batch can exceed the YouTube daily API quota
(~10k units, 50 per title update ≈ ~180 titles/day); every job is idempotent, so just
re-run the next day to finish.

## Architecture

Pure logic (`dates`, `matching`, `retitle`, `notify`) is unit-tested and network-free.
`youtube`/`telegram` are thin wrappers. `jobs` orchestrates; `main` is the CLI entrypoint the
workflow invokes. See `docs/superpowers/specs/` and `docs/superpowers/plans/` for design.
