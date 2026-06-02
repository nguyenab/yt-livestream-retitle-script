---
id: 0010
iteration: 10
date: 2026-06-02T09:48:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
Track 3's last open item: the plan's "optional rotating file handler for logs/app.log". In
iteration 9 I noted this leaned YAGNI because systemd/journald already captures and rotates
stdout. Resolution: make it genuinely optional and off by default, so it adds a real choice for
non-systemd deployments without imposing files on the journald path. Going in: 67 tests green.

## Decision
Added an optional `LOG_FILE` env var (`config.log_file`, default `""`). When set, the daemon
attaches a `RotatingFileHandler` (1 MB x 5 backups, standard format) to the root logger in
addition to stdout. Factored the format string into `_LOG_FORMAT` and added a testable
`_make_file_handler(path, level)` factory. Documented `LOG_FILE` in `.env.example` and CLAUDE.md.
Added tests: config reads `LOG_FILE` and defaults to empty; the handler factory sets maxBytes,
backupCount, level, and target path. Off by default, so existing/systemd deployments are
unchanged. Suite: 69 passed; ruff clean.

## Alternatives
- Decline entirely (pure YAGNI): reasonable given journald, but an env-gated handler is cheap,
  covers non-systemd hosts, and changes nothing when unset — so it's strictly additive.
- Always-on file logging: rejected — would duplicate journald output and impose disk management
  on the common systemd path.

## Consequences
All three plan tracks are now complete: Track 1 (reliable uploads-playlist listing wired into the
jobs + diagnostic), Track 2 (DST, dedup, update-shape, window-edge, malformed-response tests),
Track 3 (409 alert, README, ruff config + Makefile, optional file logging). Strict mode goal is
met; the loop should write its summary and stop. Remaining real-world step is outside automation:
the live `python -m app.main list`/`backdate` verification against the actual channel.

## Links
- files: app/config.py, app/main.py, tests/test_config.py, tests/test_main.py, .env.example,
  CLAUDE.md
