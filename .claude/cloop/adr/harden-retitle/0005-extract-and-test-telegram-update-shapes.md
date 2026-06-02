---
id: 0005
iteration: 5
date: 2026-06-02T08:18:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
Track 2. The Telegram poll loop in `main()` parsed update shapes inline
(`message`/`edited_message`, then `text`) with no test coverage — a real robustness gap, since
a non-text update (photo, sticker, callback_query) flows through the live loop unmodelled.
Going in: 55 tests green.

## Decision
Extracted `_extract_command(update) -> (chat_id, text) | None` from the loop body and rewired
the loop to use it. The helper handles message and edited_message, and returns None for updates
with no message or no text. Added four tests: message, edited_message, no-message
(callback_query), and message-without-text (photo). Behavior is unchanged from the previous
inline logic; it is now isolated and covered. Suite: 59 passed.

## Alternatives
- Leave the parsing inline and test it via the loop: rejected — the `while True` poll loop is
  not unit-testable without heavy mocking; a small pure helper is the right seam.

## Consequences
Update-shape handling is now regression-protected and the loop body is a few lines shorter and
clearer. Track 2 remaining: malformed/empty API responses (e.g. liveBroadcasts/videos returning
no `items`) and `decide()` window-boundary exactness (a stream exactly at the window edge).

## Links
- files: app/main.py, tests/test_main.py
