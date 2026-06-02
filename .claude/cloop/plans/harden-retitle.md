---
slug: harden-retitle
mode: strict
interval: 18m
max_iterations: 15
roles: [planner, worker, qa, scribe]
commit_style: conventional-context
criteria_ref: null
---

# Goal

Harden and finish the YouTube livestream auto-retitle service (already shipped: 44 passing
tests, daemon + scheduler + Telegram control). Work through three tracks in priority order,
keeping the test suite green and the tree committable after every iteration.

## Track 1 — Uploads-playlist fallback listing (highest value)

The jobs currently find streams only via `liveBroadcasts.list`. Per the final review, a
legacy persistent stream key can mean Streamlabs broadcasts never surface there, making the
jobs a silent no-op (`Scanned: 0`). Add a reliable fallback:

- New listing path in `app/youtube.py`: enumerate the channel's **uploads playlist**
  (`channels.list(part=contentDetails)` → `relatedPlaylists.uploads` →
  `playlistItems.list`), then `videos.list(part=snippet,liveStreamingDetails)` and keep
  only items that have `liveStreamingDetails` (i.e. were livestreams, never plain uploads).
- Wire it into `jobs.py` so **backdate** can use the uploads-playlist source (most reliable
  for completed history) while **weekly** keeps `liveBroadcasts.list` for upcoming/active
  streams, optionally unioning both. Preserve the "livestreams only" guarantee.
- TDD with mocked service objects; keep `start_iso` semantics (actualStartTime fallback
  scheduledStartTime). Watch quota cost and document it.

## Track 2 — Broaden test coverage

Add edge-case tests the mocked suite doesn't yet reach: DST spring-forward/fall-back date
formatting, multi-page pagination + the `seen` dedupe, items missing start times, malformed
/ empty API responses, Telegram `edited_message` and non-text update shapes, the retry path,
and `decide()` window boundaries (exactly at the edge). Fix any real bugs the new tests expose.

## Track 3 — General hardening & polish

- Treat a persistent Telegram `getUpdates` 409 (two pollers on one token) as a fatal
  misconfiguration alert instead of silent 10s backoff forever.
- Structured logging niceties + optional rotating file handler for `logs/app.log`.
- Add `ruff` config + a `make test`/`make lint` or simple dev script; a short `README.md`.
- Any small robustness fixes surfaced along the way.

# Scope and notes

- Stay green: `.venv/bin/python -m pytest` must pass at the end of every iteration before commit.
- Keep modules small and single-purpose; follow existing patterns and the design spec in
  `docs/superpowers/specs/`.
- No real network calls in tests — mock `googleapiclient`/`requests` as the existing tests do.
- Do not touch `.env`, secrets, or push to any remote. Commit locally only.
- Strict mode: when all three tracks are done (or `max_iterations` reached), write the
  summary and stop.
