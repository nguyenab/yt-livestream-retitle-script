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
7) and `DRY_RUN` can be set as env in the workflow if needed.

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
read-only — it lists the livestreams that are neither dated nor on the allowlist (the
candidates for the curated repair list), printing them to the Actions log and writing
`review_candidates.csv` (uploaded as a workflow artifact). Each row carries a `weekday`
column so non-Sunday streams (not worship services) are easy to filter out. Output path
overridable via `REVIEW_OUTPUT_FILE`.

## How it decides what to retitle

1. List livestreams via `liveBroadcasts.list` unioned with the uploads playlist (filtered to
   videos with `liveStreamingDetails`), deduped by video id — never plain uploads.
2. Skip any title that already starts with a date prefix (idempotent).
3. Match remaining titles against `BASE_TITLES` (diacritic/case/whitespace-insensitive).
   `BASE_TITLES` is an allowlist of titles that are already correct.
4. Prepend that stream's own date — `actualStartTime` (fallback `scheduledStartTime`),
   converted **UTC → Pacific** — as `Weekday, Month Dayth, Year - `.

Any title that is **not** on the allowlist is left untouched — the tool never guesses
that an arbitrary title is a mis-titled worship stream, because many livestreams
legitimately have their own titles (weekday studies, special events, etc.).

### Curated repair list (`force_retitle_ids.txt`)

For streams a team member **wrongly** retitled (e.g. pasted a sermon passage over a
worship stream), list their video ids in `force_retitle_ids.txt` (one per line, `#`
comments allowed). Each listed id is rewritten to `<its own broadcast date> -
<canonical>`, where canonical is the **first** `BASE_TITLES` entry — regardless of its
current title or any existing (wrong) date prefix. It's idempotent and exempt from the
recency window. The Telegram report flags these replaced titles (`✎`) separately from
dated-only ones (`•`). Replacement runs in `weekly` and `backdate` (not the `run_job`
diagnostic path). Adding an id is a deliberate, version-controlled decision; the file
path is overridable via `FORCE_RETITLE_IDS_FILE`.

Weekly run looks back `RECENT_WINDOW_DAYS`; backdate scans all history. Run a
`backdate` with `DRY_RUN=true` first to preview before writing.

## Architecture

Pure logic (`dates`, `matching`, `retitle`, `notify`) is unit-tested and network-free.
`youtube`/`telegram` are thin wrappers. `jobs` orchestrates; `main` is the CLI entrypoint the
workflow invokes. See `docs/superpowers/specs/` and `docs/superpowers/plans/` for design.
