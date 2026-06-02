---
id: 0001
iteration: 1
date: 2026-06-02T07:10:22Z
plan_slug: harden-retitle
qa: pass
---

## Context
Track 1 of the plan (highest value). The jobs find streams only via `liveBroadcasts.list`,
which the final review flagged can silently miss Streamlabs broadcasts created against a
legacy persistent stream key — leaving the jobs a no-op (`Scanned: 0`). Going in: 44 tests
green, clean tree. This iteration builds the reliable listing primitive; wiring it into the
jobs is the next step.

## Decision
Added `list_livestreams_via_uploads(service)` to `app/youtube.py`. It resolves the channel's
uploads playlist (`channels.list(part=contentDetails, mine=true)` →
`relatedPlaylists.uploads`), paginates `playlistItems.list` for all video ids, then
batches `videos.list(part=snippet,liveStreamingDetails)` (50 ids/call). It keeps a video
only if it carries a `liveStreamingDetails` block — preserving the "livestreams only"
guarantee — and extracts `start_iso` as actualStartTime with scheduledStartTime fallback,
matching the existing `list_broadcasts` tuple shape `(video_id, title, start_iso)` so it is
drop-in for `jobs.py`. Covered by 4 mocked tests (filtering out plain uploads, pagination +
scheduled fallback, empty channel, livestream missing start). Suite: 48 passed.

## Alternatives
- `search.list(forMine=true, eventType=completed)`: simpler but costs ~100 quota units/call
  and is eventually-consistent. Rejected in favor of the cheaper, deterministic playlist walk.
- Wiring into `jobs.py` this same iteration: deferred to keep the step coherent and the diff
  reviewable; the primitive lands and is tested first.

## Consequences
The reliable listing path now exists and is tested. Next iteration: wire it into
`backdate_all` (best source for completed history) while `weekly_job` keeps
`liveBroadcasts.list` for upcoming/active streams — likely a union with dedupe by video id.
Still needs a live `python -m app.main list` check against the real channel once wired.

## Links
- files: app/youtube.py, tests/test_youtube.py
