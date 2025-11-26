r"""Compare baseline (no advanced/LLM features) vs advanced models for a small roster.

Trains a baseline model where advanced and LLM-derived features are zeroed,
and an advanced model with the real features. Uses chronological split to
evaluate on the validation set and writes a CSV report to
`backend/models_store/compare_report_<timestamp>.csv`.

Usage example (PowerShell from repo root):

    $env:PYTHONPATH='.'; & .\.venv\Scripts\python.exe backend\scripts\compare_advanced_vs_baseline.py --players "Stephen Curry,LeBron James" --min-games 1
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
from typing import List

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error

from backend.scripts.retrain_with_advanced_features import augment_with_llm
from backend.services import training_data_service, training_pipeline

logger = logging.getLogger("compare_adv_vs_baseline")
logging.basicConfig(level=logging.INFO)


def zero_advanced_and_llm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # columns to zero: any starting with adv_ or multi_, plus common LLM cols
    to_zero = [c for c in df.columns if c.startswith("adv_") or c.startswith("multi_")]
    llm_cols = ["injury_sentiment", "morale_score", "motivation"]
    for c in llm_cols:
        if c in df.columns:
            to_zero.append(c)

    # ensure uniqueness
    to_zero = list(set(to_zero))
    for c in to_zero:
        try:
            df[c] = 0.0
        except Exception:
            df[c] = 0.0
    return df


def evaluate_player(player: str, min_games: int = 1) -> dict:
    try:
        df = training_data_service.generate_training_data(
            player, min_games=min_games, fetch_limit=300
        )
    except Exception as e:
        logger.exception("Failed to generate training data for %s", player)
        return {"player": player, "status": "no_data"}

    # augment with LLM features (deterministic placeholder when no news)
    df_adv = augment_with_llm(df, player)

    # split chronologically
    try:
        train_df, val_df, test_df = training_data_service.chronological_split_by_ratio(
            df_adv, date_col="game_date", train_frac=0.7, val_frac=0.15, test_frac=0.15
        )
    except Exception:
        # fallback: simple train/val split
        n = len(df_adv)
        if n < 2:
            return {"player": player, "status": "insufficient_rows", "n_rows": n}
        train_end = int(max(1, round(n * 0.7)))
        train_df = df_adv.iloc[:train_end]
        val_df = df_adv.iloc[train_end : train_end + max(1, int(round(n * 0.15)))]

    if len(train_df) < 3 or len(val_df) < 1:
        return {"player": player, "status": "insufficient_rows", "n_rows": len(df_adv)}

    # baseline: zero advanced and LLM features
    train_base = zero_advanced_and_llm(train_df)
    val_base = zero_advanced_and_llm(val_df)

    # advanced: use real features (train_df / val_df)
    # Train models
    try:
        model_adv = training_pipeline.train_player_model(train_df, target_col="target")
    except Exception:
        logger.exception("Advanced training failed for %s", player)
        return {"player": player, "status": "train_fail_adv"}

    try:
        model_base = training_pipeline.train_player_model(
            train_base, target_col="target"
        )
    except Exception:
        logger.exception("Baseline training failed for %s", player)
        return {"player": player, "status": "train_fail_base"}

    # Prepare validation matrices matching training columns
    def prepare_X(df_source, train_reference):
        X = (
            df_source.drop(columns=["target"], errors="ignore")
            .select_dtypes(include=[np.number])
            .copy()
        )
        # align columns to training X
        train_cols = list(
            train_reference.drop(columns=["target"], errors="ignore")
            .select_dtypes(include=[np.number])
            .columns
        )
        for c in train_cols:
            if c not in X.columns:
                X[c] = 0.0
        X = X[train_cols]
        X = X.fillna(0.0)
        return X

    X_val_adv = prepare_X(val_df, train_df)
    y_val = val_df["target"].astype(float)

    X_val_base = prepare_X(val_base, train_base)

    # Predict
    try:
        ypred_adv = model_adv.predict(X_val_adv)
        ypred_base = model_base.predict(X_val_base)
    except Exception:
        logger.exception("Prediction failed for %s", player)
        return {"player": player, "status": "predict_fail"}

    mse_adv = float(mean_squared_error(y_val, ypred_adv))
    mse_base = float(mean_squared_error(y_val, ypred_base))
    rmse_adv = float(np.sqrt(mse_adv))
    rmse_base = float(np.sqrt(mse_base))

    return {
        "player": player,
        "status": "ok",
        "n_rows": len(df_adv),
        "rmse_advanced": rmse_adv,
        "rmse_baseline": rmse_base,
        "delta_rmse": rmse_base - rmse_adv,
    }


def main(players: List[str], min_games: int = 1, out_dir: str = "backend/models_store"):
    results = []
    for p in players:
        logger.info("Evaluating player: %s", p)
        r = evaluate_player(p, min_games=min_games)
        results.append(r)

    df = pd.DataFrame(results)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"compare_report_{ts}.csv")
    df.to_csv(out_path, index=False)
    logger.info("Wrote report to %s", out_path)
    print(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare advanced vs baseline models for a roster"
    )
    parser.add_argument("--players", default=None, help="Comma-separated player list")
    parser.add_argument("--min-games", type=int, default=1)
    args = parser.parse_args()

    default_players = [
        "LeBron James",
        "Stephen Curry",
        "Luka Doncic",
        "Kevin Durant",
        "Jayson Tatum",
    ]

    if args.players:
        players = [p.strip() for p in args.players.split(",") if p.strip()]
    else:
        players = default_players

    main(players, min_games=args.min_games)
