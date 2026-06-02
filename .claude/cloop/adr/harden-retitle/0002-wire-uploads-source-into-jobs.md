---
id: 0002
iteration: 2
date: 2026-06-02T07:30:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
ADR 0001 added `list_livestreams_via_uploads` but left it unwired. Track 1 is only valuable
once the jobs actually use it. Going in: 48 tests green.

## Decision
Refactored `app/jobs.py` to separate listing from execution:
- `_collect(sources)` runs a list of listing thunks, unions the rows, and dedupes by
  video_id (first occurrence wins).
- `_execute(service, config, broadcasts, window_days)` holds the unchanged decide→apply loop.
- `run_job` is kept (single liveBroadcasts source) for back-compat so existing tests and the
  diagnostic path are unaffected.
- `weekly_job` now unions `liveBroadcasts.list(["all"])` (for upcoming/active) with the
  uploads playlist (for recently-completed), windowed by `recent_window_days`.
- `backdate_all` unions the uploads playlist (primary, reliable for history) with
  `liveBroadcasts.list(["completed"])`, no window.
Added two tests asserting union + dedupe for both jobs. Suite: 50 passed.

## Alternatives
- Replace `liveBroadcasts` entirely with the uploads source: rejected — uploads playlist does
  not contain upcoming/active broadcasts the weekly job must catch before they air.
- Change `run_job`'s signature to take sources: rejected — would churn the existing job tests
  for no benefit; keeping it as the single-source path is cleaner.

## Consequences
Both jobs now self-heal against streams missing from `liveBroadcasts`, deduped so a stream in
both sources is processed once. Quota per run rises modestly (channels + playlistItems +
videos batches). Follow-up: the `list` diagnostic in `main.py` still shows only liveBroadcasts;
extending it to also print the uploads source would make the live verification step more
complete. Live `python -m app.main list`/`backdate` check against the real channel still pending.

## Links
- files: app/jobs.py, tests/test_jobs.py
