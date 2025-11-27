"""Simple latency profiler for feature engineering + prediction path.

Runs `engineer_features` on a synthetic player_data payload multiple times and
measures durations. Writes a JSON report to `backend/artifacts/latency_report.json`.
"""

from __future__ import annotations

import json
import statistics
import time

from backend.services.feature_engineering import engineer_features

SAMPLE_PLAYER = {
    "playerName": "Test Player",
    "player_id": "test_123",
    "seasonAvg": 20.0,
    "recentGames": [
        {
            "statValue": 22,
            "date": "2025-11-21",
            "opponentTeamId": "TEAM1",
            "opponentDefRating": 105,
        },
        {
            "statValue": 18,
            "date": "2025-11-19",
            "opponentTeamId": "TEAM2",
            "opponentDefRating": 108,
        },
        {
            "statValue": 25,
            "date": "2025-11-17",
            "opponentTeamId": "TEAM3",
            "opponentDefRating": 102,
        },
        {
            "statValue": 15,
            "date": "2025-11-15",
            "opponentTeamId": "TEAM4",
            "opponentDefRating": 110,
        },
        {
            "statValue": 30,
            "date": "2025-11-13",
            "opponentTeamId": "TEAM5",
            "opponentDefRating": 99,
        },
    ],
    "advancedStatsMulti": {
        "aggregated": {"PER": 19.2, "TS_PCT": 0.585, "USG_PCT": 23.0}
    },
}


def profile(n_iters: int = 200):
    durations = []
    for i in range(n_iters):
        t0 = time.perf_counter()
        _ = engineer_features(SAMPLE_PLAYER)
        t1 = time.perf_counter()
        durations.append((t1 - t0) * 1000.0)  # ms

    report = {
        "n_iters": n_iters,
        "mean_ms": statistics.mean(durations),
        "median_ms": statistics.median(durations),
        "p95_ms": statistics.quantiles(durations, n=100)[94],
        "min_ms": min(durations),
        "max_ms": max(durations),
    }

    out_path = "backend/artifacts/latency_report.json"
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"Wrote latency report to {out_path}")
    except Exception:
        print(report)

    print("Summary:")
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    profile(200)
