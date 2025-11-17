"""Lightweight monitoring helpers for model artifacts and training summaries.

This module provides utilities to aggregate fallback coverage and calibration
statistics from training outputs (e.g., the JSON summary written by
`backend/training/train_models.py`). It's intentionally minimal so CI or
ops scripts can call it to produce quick reports.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


def aggregate_training_summary(summary_path: str) -> Dict[str, Any]:
    p = Path(summary_path)
    if not p.exists():
        raise FileNotFoundError(summary_path)
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    players = list(data.items())
    n_players = len(players)
    if n_players == 0:
        return {"n_players": 0}

    sum_pct_with_last5 = 0.0
    sum_pct_with_last3 = 0.0
    sum_pct_with_season = 0.0
    sum_pct_fully_missing = 0.0

    count_with_calib = 0
    calib_ece_sum = 0.0

    per_player = []
    for player_name, meta in players:
        # metadata saved by train_models stores fallback_coverage under model metadata
        m = meta.get("metrics") or {}
        # try various places where fallback_coverage might exist
        fcov = None
        # prefer top-level if present
        if isinstance(meta, dict) and meta.get("fallback_coverage"):
            fcov = meta.get("fallback_coverage")
        else:
            # some callers place metadata deeper; check common locations
            if isinstance(meta, dict):
                for key in ("metadata", "model_metadata", "metrics"):
                    if isinstance(meta.get(key), dict) and meta.get(key).get("fallback_coverage"):
                        fcov = meta.get(key).get("fallback_coverage")
                        break

        if not fcov:
            # fallback: attempt to inspect `meta` for known keys inside registry index
            fcov = meta.get("fallback_coverage") if isinstance(meta, dict) else None

        if fcov:
            sum_pct_with_last5 += float(fcov.get("pct_with_last5", 0.0))
            sum_pct_with_last3 += float(fcov.get("pct_with_last3", 0.0))
            sum_pct_with_season += float(fcov.get("pct_with_seasonAvg", 0.0))
            sum_pct_fully_missing += float(fcov.get("pct_fully_missing", 0.0))
            per_player.append({
                "player": player_name,
                "pct_with_last5": float(fcov.get("pct_with_last5", 0.0)),
                "pct_with_last3": float(fcov.get("pct_with_last3", 0.0)),
                "pct_with_seasonAvg": float(fcov.get("pct_with_seasonAvg", 0.0)),
                "pct_fully_missing": float(fcov.get("pct_fully_missing", 0.0)),
            })

        # calibration: if present under calibration -> calibrated.ece
        calib = None
        if isinstance(meta, dict):
            calib = meta.get("calibration")
        if calib and isinstance(calib, dict):
            raw = calib.get("raw")
            if raw and raw.get("ece") is not None:
                try:
                    calib_ece_sum += float(raw.get("ece"))
                    count_with_calib += 1
                except Exception:
                    pass

    return {
        "n_players": n_players,
        "avg_pct_with_last5": round(sum_pct_with_last5 / n_players, 4),
        "avg_pct_with_last3": round(sum_pct_with_last3 / n_players, 4),
        "avg_pct_with_seasonAvg": round(sum_pct_with_season / n_players, 4),
        "avg_pct_fully_missing": round(sum_pct_fully_missing / n_players, 4),
        "players_with_calibration": count_with_calib,
        "avg_raw_ece": round((calib_ece_sum / count_with_calib) if count_with_calib else 0.0, 6),
        "per_player": per_player,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("summary", help="Path to training_summary JSON produced by train_models")
    args = parser.parse_args()
    out = aggregate_training_summary(args.summary)
    print(json.dumps(out, indent=2))
