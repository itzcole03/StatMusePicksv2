#!/usr/bin/env python3
"""CLI entrypoint to run the daily ingestion sync.

Usage:
  python -m backend.cli.run_daily_sync --when  # optional ISO date (YYYY-MM-DD)

This module calls `run_daily_sync_async()` from the ingestion service and
returns non-zero exit codes on failure so it can be used in cron/systemd.
"""
import sys
import argparse
import asyncio
import json
import logging
from datetime import datetime

from backend.services import data_ingestion_service as ingest

logger = logging.getLogger("run_daily_sync")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Run the daily data ingestion sync")
    p.add_argument("--when", help="Optional date (YYYY-MM-DD) to run for", default=None)
    p.add_argument("--dry-run", help="Perform a dry run (no DB/audit/alerting)", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    when = None
    if args.when:
        try:
            when = datetime.fromisoformat(args.when).date()
        except Exception:
            logger.error("Invalid --when value, expected YYYY-MM-DD")
            return 2

    try:
        # prefer the async entrypoint
        # Prefer the async entrypoint and pass through dry_run flag.
        try:
            result = asyncio.run(ingest.run_daily_sync_async(when, dry_run=args.dry_run))
        except RuntimeError:
            # We're inside an event loop or asyncio.run failed; fall back to sync wrapper
            result = ingest.run_daily_sync(when, dry_run=args.dry_run)
    except Exception as exc:  # pragma: no cover - operational wrapper
        logger.exception("run_daily_sync failed: %s", exc)
        # best-effort alerting (may itself fail)
        try:
            summary = {"error": str(exc), "when": str(when)}
            # data_ingestion_service.send_alert is best-effort and robust
            ingest.send_alert(json.dumps(summary))
        except Exception:
            logger.exception("send_alert failed while reporting ingestion failure")
        return 1

    # If dry-run, communicate via exit code 0 and print result
    try:
        if args.dry_run and 'result' in locals():
            logger.info("dry-run result: %s", result)
    except Exception:
        pass

    logger.info("run_daily_sync completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
