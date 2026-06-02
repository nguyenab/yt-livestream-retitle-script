---
id: 0006
iteration: 6
date: 2026-06-02T08:36:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
Track 2's last named gaps: `decide()` window-boundary exactness and malformed/empty API
responses. The window uses a strict `<` comparison (`start < ref - timedelta(days=window)`),
so edge behavior (a stream exactly at the cutoff) was unspecified by tests; and the listing
helpers rely on `.get("items", [])` defenses that were never exercised against a response
missing the key. Going in: 59 tests green.

## Decision
Added five characterization tests (no production code changed):
- `retitle`: a stream exactly `window_days` old is included (strict `<` excludes only older);
  a stream one second past the edge is excluded.
- `youtube`: `list_broadcasts` returns [] when a page lacks an `items` key;
  `list_livestreams_via_uploads` returns [] when `videos.list` yields no items;
  `get_video_snippet` returns None when the response has no items.
All five passed against current code. Suite: 64 passed.

## Alternatives
- Tighten the window to inclusive/exclusive differently: rejected — current strict `<` (include
  exactly-at-edge) is sensible and now documented by tests; no behavior change warranted.

## Consequences
Track 2 (broaden test coverage) is complete: DST boundaries, cross-status dedup, Telegram update
shapes, window edges, and malformed responses are all covered. No bugs surfaced — the defensive
code held. Next: Track 3 (general hardening) — starting with treating a persistent Telegram 409
(two pollers on one token) as a fatal alert instead of silent backoff.

## Links
- files: tests/test_retitle.py, tests/test_youtube.py
