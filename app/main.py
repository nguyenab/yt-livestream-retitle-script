from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import state as state_mod
from app import telegram, youtube
from app.config import Config, load_config
from app.jobs import JobReport, backdate_all, weekly_job
from app.notify import format_report, format_status

log = logging.getLogger("yt-retitle")

HELP_TEXT = (
    "Commands:\n"
    "/status — last run, next run, errors\n"
    "/run — run the weekly job now\n"
    "/backdate — retitle all past livestreams (idempotent)\n"
    "/help — this message"
)


@dataclass
class Context:
    config: Config
    service: object
    scheduler: object
    started_at: str
    send: Callable[[str], None]
    next_run: Callable[[], str]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _record(report: JobReport) -> None:
    state = state_mod.load_state()
    state["last_run_at"] = _now_iso()
    state["last_result"] = f"changed {report.changed}, failures {len(report.failures)}"
    state["last_error"] = report.failures[0] if report.failures else None
    state_mod.save_state(state)


def _run_and_report(ctx: Context, title: str, fn) -> None:
    try:
        report = fn(ctx.service, ctx.config)
        _record(report)
        ctx.send(format_report(title, report))
    except Exception as e:  # noqa: BLE001 - never let a job crash the daemon
        log.exception("%s failed", title)
        state = state_mod.load_state()
        state["last_error"] = f"{title}: {e}"
        state_mod.save_state(state)
        ctx.send(f"⚠ {title} failed: {e}")


def handle_command(ctx: Context, chat_id: str, text: str) -> None:
    if str(chat_id) != str(ctx.config.telegram_chat_id):
        log.warning("ignoring command from unauthorized chat %s", chat_id)
        return
    cmd = text.strip().split()[0].lower() if text.strip() else ""
    if cmd == "/status":
        ctx.send(format_status(state_mod.load_state(), ctx.next_run(), ctx.started_at))
    elif cmd == "/help":
        ctx.send(HELP_TEXT)
    elif cmd == "/run":
        ctx.send("Running weekly job…")
        _run_and_report(ctx, "Weekly run (manual)", weekly_job)
    elif cmd == "/backdate":
        ctx.send("Starting backdate of all past livestreams…")
        _run_and_report(ctx, "Backdate", backdate_all)
    else:
        ctx.send(f"Unknown command: {cmd}\n\n{HELP_TEXT}")


def _scheduled_weekly(ctx: Context) -> None:
    _run_and_report(ctx, "Weekly run", weekly_job)


def _extract_command(update: dict):
    """Pull (chat_id, text) from a Telegram update, or None if it carries no text command.

    Handles both message and edited_message; ignores updates with no message (callbacks,
    channel posts) and messages with no text (photos, stickers).
    """
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None
    text = msg.get("text", "")
    if not text:
        return None
    return msg.get("chat", {}).get("id"), text


def _is_conflict(exc) -> bool:
    """True if exc is a Telegram getUpdates 409 Conflict (another poller on this token)."""
    resp = getattr(exc, "response", None)
    return getattr(resp, "status_code", None) == 409


def collect_diagnostics(service) -> dict[str, list]:
    """Gather what each listing source returns, for the `list` diagnostic command.

    Lets you confirm whether the uploads-playlist source catches streams that
    liveBroadcasts.list misses, before trusting the jobs against the real channel.
    """
    return {
        "liveBroadcasts (all)": youtube.list_broadcasts(service, ["all"]),
        "uploads playlist (livestreams)": youtube.list_livestreams_via_uploads(service),
    }


def _drain_pending_updates(token: str) -> int | None:
    """Consume updates queued while the daemon was down so old commands don't replay.

    Without this, a /backdate sent (or left unread) while the service was offline would
    auto-fire on the next startup. Returns the offset to resume from (last update_id + 1),
    or None if nothing was pending.
    """
    try:
        updates = telegram.get_updates(token, offset=None, timeout=0)
    except Exception:  # noqa: BLE001 - draining is best-effort
        log.exception("failed to drain pending updates at startup")
        return None
    if not updates:
        return None
    log.info("dropped %d pending Telegram update(s) at startup", len(updates))
    return updates[-1]["update_id"] + 1


def main() -> None:
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    service = youtube.build_service(
        config.youtube_client_id,
        config.youtube_client_secret,
        config.youtube_refresh_token,
    )

    scheduler = BackgroundScheduler(timezone=config.timezone)

    def next_run() -> str:
        jobs = scheduler.get_jobs()
        if jobs and jobs[0].next_run_time:
            return jobs[0].next_run_time.strftime("%Y-%m-%d %H:%M %Z")
        return "unscheduled"

    def send(text: str) -> None:
        try:
            telegram.send_message(config.telegram_bot_token, config.telegram_chat_id, text)
        except Exception:  # noqa: BLE001
            log.exception("failed to send Telegram message")

    ctx = Context(
        config=config,
        service=service,
        scheduler=scheduler,
        started_at=_now_iso(),
        send=send,
        next_run=next_run,
    )

    scheduler.add_job(
        lambda: _scheduled_weekly(ctx),
        CronTrigger(
            day_of_week=config.schedule_day,
            hour=config.schedule_hour,
            minute=0,
            timezone=ZoneInfo(config.timezone),
        ),
        id="weekly",
    )
    scheduler.start()
    send(f"✅ yt-retitle started. Next weekly run: {next_run()}"
         + (" (DRY_RUN)" if config.dry_run else ""))

    offset = _drain_pending_updates(config.telegram_bot_token)
    conflict_alerted = False
    log.info("entering Telegram poll loop")
    while True:
        try:
            updates = telegram.get_updates(config.telegram_bot_token, offset=offset, timeout=30)
            conflict_alerted = False  # cleared once polling succeeds again
            for upd in updates:
                offset = upd["update_id"] + 1
                parsed = _extract_command(upd)
                if parsed is None:
                    continue
                handle_command(ctx, parsed[0], parsed[1])
        except Exception as e:  # noqa: BLE001 - keep polling through transient errors
            if _is_conflict(e):
                log.error("Telegram 409 Conflict — another poller holds this bot token")
                if not conflict_alerted:
                    send(
                        "⚠ Telegram conflict (409): another process is polling this bot token. "
                        "Only one yt-retitle instance may run — stop the duplicate."
                    )
                    conflict_alerted = True
                time.sleep(30)
            else:
                log.exception("poll loop error; backing off 10s")
                time.sleep(10)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YouTube livestream auto-retitle")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["serve", "backdate", "weekly", "list"],
        default="serve",
        help="serve (default daemon), backdate (one-shot), weekly (one-shot), "
        "list (diagnostic: print livestreams the API returns, no changes)",
    )
    args = parser.parse_args()

    if args.command == "serve":
        main()
        sys.exit(0)

    cfg = load_config()
    logging.basicConfig(level=getattr(logging, cfg.log_level, logging.INFO), stream=sys.stdout)
    svc = youtube.build_service(
        cfg.youtube_client_id, cfg.youtube_client_secret, cfg.youtube_refresh_token
    )

    if args.command == "list":
        # Diagnostic: confirm the channel's livestreams (incl. Streamlabs-created ones)
        # surface via each source before trusting backdate/weekly. Compare the two:
        # if uploads shows streams liveBroadcasts misses, the jobs now still catch them.
        for label, rows in collect_diagnostics(svc).items():
            print(f"\n=== {label} — {len(rows)} ===")
            for vid, title, start in rows:
                print(f"{start}  {vid}  {title}")
    else:
        fn = backdate_all if args.command == "backdate" else weekly_job
        rep = fn(svc, cfg)
        print(format_report(args.command, rep))
        try:
            telegram.send_message(
                cfg.telegram_bot_token, cfg.telegram_chat_id, format_report(args.command, rep)
            )
        except Exception:  # noqa: BLE001
            log.exception("failed to send Telegram report")
