"""Simple training script: generate training data for one player and train a baseline model.

Saves model to `backend/models_store/{player_name}.pkl` and prints a brief report.
"""

import argparse
import json
from pathlib import Path

import joblib

from backend.services.training_data_service import generate_training_data


def safe_filename(name: str) -> str:
    return name.replace(" ", "_")


def train_and_persist(player: str, stat: str = "points"):
    print(f"Generating training data for {player} ({stat})...")
    try:
        df = generate_training_data(player, stat=stat, min_games=20, fetch_limit=500)
        print(f"Generated {len(df)} training rows")
    except Exception as e:
        print(f"Failed to generate training data: {e}")
        # Fallback: create a tiny synthetic dataset so CI/dev runs can still produce a model
        import numpy as np

        print("Falling back to synthetic data for training...")
        rng = np.random.default_rng(42)
        n = 200
        recent_mean = rng.normal(20, 5, size=n)
        recent_std = rng.normal(3, 1, size=n)
        days_rest = rng.integers(0, 4, size=n)
        is_home = rng.integers(0, 2, size=n)
        opp_def = rng.normal(105, 3, size=n)
        target = recent_mean * 0.8 + recent_std * 0.3 + rng.normal(0, 2, size=n)
        import pandas as _pd

        df = _pd.DataFrame(
            {
                "last_3_avg": recent_mean,
                "last_5_avg": recent_mean + rng.normal(0, 1, size=n),
                "last_10_avg": recent_mean + rng.normal(0, 1, size=n),
                "last_3_std": recent_std,
                "days_rest": days_rest,
                "is_home": is_home,
                "opp_def": opp_def,
                "target": target,
            }
        )
        print(f"Synthetic dataset created ({len(df)} rows)")

    X = df[
        [
            "last_3_avg",
            "last_5_avg",
            "last_10_avg",
            "last_3_std",
            "days_rest",
            "is_home",
            "opp_def",
        ]
    ]
    y = df["target"]

    try:
        from sklearn.ensemble import RandomForestRegressor
    except Exception as e:
        print("scikit-learn not installed; writing placeholder model metadata instead")
        out_dir = Path("backend/models_store")
        out_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "player": player,
            "stat": stat,
            "rows": len(df),
            "note": "sklearn missing; no model trained",
        }
        with open(out_dir / f"{safe_filename(player)}.meta.json", "w") as f:
            json.dump(meta, f)
        print("Wrote metadata to models_store")
        return

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    out_dir = Path("backend/models_store")
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / f"{safe_filename(player)}.pkl"
    joblib.dump(model, model_path)

    meta = {
        "player": player,
        "stat": stat,
        "rows": len(df),
        "model_path": str(model_path),
    }
    with open(out_dir / f"{safe_filename(player)}.meta.json", "w") as f:
        json.dump(meta, f)

    print(f"Saved model to {model_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True)
    parser.add_argument("--stat", default="points")
    args = parser.parse_args()
    train_and_persist(args.player, args.stat)
