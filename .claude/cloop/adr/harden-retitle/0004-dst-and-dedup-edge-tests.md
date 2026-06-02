---
id: 0004
iteration: 4
date: 2026-06-02T08:00:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
Track 1 complete; moving to Track 2 (broaden test coverage). The happy-path suite never
exercised the daylight-saving boundaries — the exact case the spec calls out ("6 PST vs PDT")
— nor the cross-status dedup in `list_broadcasts`. These are the highest-risk untested paths.
Going in: 51 tests green.

## Decision
Added four characterization tests (no production code changed):
- `dates`: fall-back instant (2026-11-01 07:30Z → 00:30 PDT) must stay Nov 1, proving PDT is
  applied rather than naive PST (which would roll to Oct 31); spring-forward morning
  (2026-03-08 09:30Z → 01:30 PST) stays Mar 8; a tz-naive datetime is treated as UTC.
- `youtube`: a video id appearing under two requested broadcast statuses is returned once.
All four passed immediately — existing behavior is correct; the tests lock it against
regression. Suite: 55 passed.

## Alternatives
- Skip DST tests as "obviously handled by zoneinfo": rejected — the spec explicitly flagged
  PST/PDT as a correctness risk, so it deserves an explicit guard.

## Consequences
DST and dedup behavior are now regression-protected. No bug surfaced, so no fix needed. Track 2
continues next: malformed/empty API responses, Telegram `edited_message`/non-text update
shapes, and `decide()` window-boundary exactness.

## Links
- files: tests/test_dates.py, tests/test_youtube.py
