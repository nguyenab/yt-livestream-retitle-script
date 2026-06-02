---
id: 0009
iteration: 9
date: 2026-06-02T09:30:00Z
plan_slug: harden-retitle
qa: pass
---

## Context
Track 3 (polish): no linter config or dev script existed. Going in: 67 tests green, ruff not
installed.

## Decision
Added `pyproject.toml` with a pragmatic, low-noise ruff config (`select = E,F,I,B,UP`,
line-length 100, `target-version py311`, and `tests/* ignore E501` since test fixtures use long
inline JSON literals). Added a `Makefile` with `test`, `lint`, `fmt`, `check` targets, and added
`ruff>=0.6` to requirements as a dev tool. Ran `ruff check --fix`, which applied 24 safe fixes
(import sorting; `pyupgrade` rewrites: `datetime.now(timezone.utc)` → `datetime.now(UTC)` and
`from typing import Callable` → `from collections.abc import Callable`). Manually shortened one
over-length log line in `main.py`. Final: `ruff check .` clean, 67 tests still pass, app imports.

## Decision check
- `ruff check .` → All checks passed.
- `pytest` → 67 passed (UP rewrites didn't change behavior).
- `make lint` runs and passes.

## Alternatives
- Broad rule set incl. BLE/RUF: rejected — produced 27 findings (RUF100 unused-noqa, RUF012
  mutable-default in test helpers) that would force churn or noqa edits across test files for no
  real benefit. The curated set keeps signal high and the diff small.

## Consequences
Lint is now enforceable (`make check` = lint + test) and the codebase is modernized to py311
datetime/typing idioms. Track 3's last open question — the optional rotating file-log handler —
is the remaining item; leaning YAGNI since systemd/journald already captures and rotates stdout.
That decision (and strict-mode completion) comes next.

## Links
- files: pyproject.toml, Makefile, requirements.txt, app/main.py, tests/test_dates.py,
  tests/test_retitle.py, tests/test_youtube.py
