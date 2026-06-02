---
id: 0007
iteration: 7
date: 2026-06-02T08:54:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
Track 3 (hardening), first item from the final review. The poll loop caught every exception,
logged it, slept 10s, and retried forever. A Telegram `409 Conflict` — raised when a second
getUpdates poller runs on the same bot token (two daemon instances) — is a persistent
misconfiguration, not a transient blip, so the loop would spin silently and commands would be
delivered to whichever instance won the race. Going in: 64 tests green.

## Decision
Added `_is_conflict(exc)` — duck-typed on `exc.response.status_code == 409`, so no `requests`
import is needed and it is trivially unit-testable. Wired the loop to branch on it: on a
conflict it logs an error, sends a one-time Telegram alert (sendMessage is unaffected by the
getUpdates conflict, so the alert reaches the user), and backs off 30s; the alert flag clears
on the next successful poll so a recurring conflict re-alerts per episode. Non-conflict errors
keep the original 10s backoff. Added 3 tests (409, other status, no response). Suite: 67 passed.

## Alternatives
- Hard-exit the daemon on conflict: rejected — systemd `Restart=always` would restart straight
  into the same conflict, producing a restart-and-alert storm. Staying alive with one clear
  alert per episode surfaces the problem without the storm.
- Import `requests` and catch `HTTPError` by type: rejected — duck typing keeps main.py free of
  the dependency and the test free of constructing a real HTTPError.

## Consequences
A duplicate-instance misconfiguration is now visible (alert + error log) instead of silent. The
daemon keeps serving in case the conflict clears. Next Track 3 items: optional rotating file log
handler, a ruff config + dev script, and a README.

## Links
- files: app/main.py, tests/test_main.py
