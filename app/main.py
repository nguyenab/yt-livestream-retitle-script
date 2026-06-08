from __future__ import annotations

import argparse
import csv
import logging
import os
import sys

from app import telegram, youtube
from app.config import load_config
from app.jobs import backdate_all, restore_titles, review_unmatched, weekly_job
from app.notify import format_report, format_review, review_csv_rows

log = logging.getLogger("yt-retitle")

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def collect_diagnostics(service) -> dict[str, list]:
    """What each listing source returns, for the `list` diagnostic command.

    Lets you confirm whether the uploads-playlist source catches streams that
    liveBroadcasts.list misses, before trusting a real run against the channel.
    """
    return {
        "liveBroadcasts (all)": youtube.list_broadcasts(service, ["all"]),
        "uploads playlist (livestreams)": youtube.list_livestreams_via_uploads(service),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube livestream auto-retitle")
    parser.add_argument(
        "command",
        choices=["backdate", "weekly", "list", "review", "restore"],
        help="backdate (full history), weekly (recent window), "
        "list (diagnostic: print livestreams each source returns; no changes), "
        "review (read-only: unmatched livestreams to a CSV + stdout; no changes), "
        "restore (set titles verbatim from restore_titles.csv — one-time un-do)",
    )
    args = parser.parse_args()

    cfg = load_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format=_LOG_FORMAT,
        stream=sys.stdout,
    )
    svc = youtube.build_service(
        cfg.youtube_client_id, cfg.youtube_client_secret, cfg.youtube_refresh_token
    )

    if args.command == "list":
        for label, rows in collect_diagnostics(svc).items():
            print(f"\n=== {label} — {len(rows)} ===")
            for vid, title, start in rows:
                print(f"{start}  {vid}  {title}")
        return

    if args.command == "review":
        rows = review_unmatched(svc, cfg)
        print(format_review(rows))
        path = os.getenv("REVIEW_OUTPUT_FILE", "review_candidates.csv").strip()
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(review_csv_rows(rows))
        log.info("wrote %d review rows to %s", len(rows), path)
        return

    if args.command == "restore":
        path = os.getenv("RESTORE_TITLES_FILE", "restore_titles.csv").strip()
        with open(path, newline="", encoding="utf-8") as f:
            overrides = [(r["video_id"], r["title"]) for r in csv.DictReader(f)]
        report = restore_titles(svc, cfg, overrides)
    else:
        fn = backdate_all if args.command == "backdate" else weekly_job
        report = fn(svc, cfg)
    text = format_report(args.command, report)
    print(text)
    try:
        telegram.send_message(cfg.telegram_bot_token, cfg.telegram_chat_id, text)
    except Exception:  # noqa: BLE001 - the run succeeded even if the notify fails
        log.exception("failed to send Telegram report")


if __name__ == "__main__":
    main()
