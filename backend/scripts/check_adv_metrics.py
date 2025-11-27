"""Resolve player IDs and fetch raw advanced metrics for inspection.

Prints JSON returned by `AdvancedMetricsService.fetch_advanced_metrics`.
Usage:
    $env:PYTHONPATH='.'; & .\.venv\Scripts\python.exe backend\scripts\check_adv_metrics.py --players "Stephen Curry,Nikola Jokic"
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import List

logger = logging.getLogger("check_adv_metrics")
logging.basicConfig(level=logging.INFO)


def get_player_id(name: str):
    try:
        from backend.services import nba_stats_client

        pid = nba_stats_client.find_player_id_by_name(name)
        return pid
    except Exception:
        logger.exception("Failed to resolve player id for %s", name)
        return None


def fetch_metrics_for(name: str):
    pid = get_player_id(name)
    if pid is None:
        print(name, "-> could not resolve id")
        return None
    try:
        from backend.services.advanced_metrics_service import create_default_service

        svc = create_default_service()
        metrics = svc.fetch_advanced_metrics(str(pid))
        print(name, "(id=", pid, ") ->")
        print(json.dumps(metrics, indent=2, default=str))
        return metrics
    except Exception:
        logger.exception("Failed to fetch advanced metrics for %s (id=%s)", name, pid)
        return None


def main(players: List[str]):
    for p in players:
        fetch_metrics_for(p)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check advanced metrics for players")
    parser.add_argument("--players", default=None, help="Comma-separated player list")
    args = parser.parse_args()

    default_players = [
        "Stephen Curry",
        "Nikola Jokic",
        "Kevin Durant",
        "Luka Doncic",
        "Devin Booker",
    ]

    if args.players:
        players = [p.strip() for p in args.players.split(",") if p.strip()]
    else:
        players = default_players

    main(players)
