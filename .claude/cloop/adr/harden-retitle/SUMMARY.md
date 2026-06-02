# harden-retitle — loop summary

**Goal:** Harden and finish the YouTube livestream auto-retitle service across three tracks.
**Mode:** strict · **Iterations run:** 10 of 15 cap · **Outcome:** completed (goal met) ·
**Tests:** 44 → 69 passing · **Lint:** ruff clean.

## What changed

### Track 1 — Reliable listing (uploads-playlist fallback)
- `0001` `b65e52c` — `list_livestreams_via_uploads()`: uploads playlist → `playlistItems` →
  `videos.list` filtered to `liveStreamingDetails` (livestreams-only, catches persistent-key
  streams `liveBroadcasts` can miss).
- `0002` `aaac387` — wired into `weekly_job`/`backdate_all` with source union + dedupe by video id.
- `0003` `49dec4d` — `list` diagnostic now compares both sources; SETUP verification updated.

### Track 2 — Broader test coverage
- `0004` `477bb02` — DST fall-back/spring-forward + naive-as-UTC date tests; cross-status dedupe.
- `0005` `73548d2` — extracted `_extract_command`; covered message/edited_message/non-text shapes.
- `0006` `c0f3b79` — `decide()` window-edge exactness + malformed/empty API response handling.

### Track 3 — Hardening & polish
- `0007` `fc326e1` — Telegram 409 conflict → one-time alert + 30s backoff (was silent retry loop).
- `0008` `c1bb657` — top-level `README.md`.
- `0009` `8cbd4c9` — ruff config (`pyproject.toml`) + `Makefile` (`make check`) + safe lint fixes.
- `0010` `c0142f9` — optional `LOG_FILE` rotating file handler (off by default; journald primary).

## Left over (cannot be automated)
- **Live channel verification.** Run `python -m app.main list` against the real channel to
  confirm the streams surface (and via which source), then a `DRY_RUN` `backdate`, before going
  live. The loop validated everything against mocks; it cannot hit the real YouTube account.

Each iteration's full reasoning is in `.claude/cloop/adr/harden-retitle/NNNN-*.md`.
