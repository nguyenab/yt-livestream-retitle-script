---
id: 0003
iteration: 3
date: 2026-06-02T07:45:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
ADR 0002 wired the uploads-playlist source into the jobs but the `list` diagnostic still
printed only liveBroadcasts (twice: all + completed). The verification step the user runs
before trusting the jobs couldn't show whether uploads catches streams liveBroadcasts misses
— which is the entire reason the fallback exists. Going in: 50 tests green.

## Decision
Added `collect_diagnostics(service)` to `app/main.py` returning a labelled dict of rows from
both sources (`liveBroadcasts (all)` and `uploads playlist (livestreams)`), and rewired the
`list` CLI branch to print them side by side. Updated `docs/SETUP.md` Step 1 to explain the
two-source output and the three interpretations (both show / only uploads shows / both empty).
Added a test asserting `collect_diagnostics` gathers both sources. Suite: 51 passed.

## Alternatives
- Keep listing only liveBroadcasts: rejected — defeats the verification purpose now that the
  jobs depend on the uploads source too.
- Print both liveBroadcasts statuses (all + completed): dropped — "all" already includes
  completed, so it was redundant; comparing liveBroadcasts vs uploads is the useful contrast.

## Consequences
The live `python -m app.main list` check now directly answers "is my channel covered?" and by
which source. Track 1 (reliable listing) is functionally complete end to end; the only
remaining piece is the user's live run against the real channel, which can't be automated here.
Next iterations move to Track 2 (broaden test coverage: DST, pagination, malformed responses).

## Links
- files: app/main.py, tests/test_main.py, docs/SETUP.md
