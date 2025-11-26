import json
import os
import random

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from backend.services import nba_service, training_data_service
from backend.services.feature_engineering import FeatureEngineering
from backend.services.model_registry import ModelRegistry


def synth_player_data():
    # create a synthetic player_data dict with recentGames of variable length
    n = random.randint(5, 12)
    recent = []
    base = random.uniform(10, 35)
    for i in range(n):
        # add some trend/noise
        val = base + (i * random.uniform(-0.5, 0.7)) + random.normalvariate(0, 3)
        recent.append(
            {"gameDate": f"2025-11-{1+i:02d}", "statValue": float(round(val, 2))}
        )
    seasonAvg = float(np.mean([g["statValue"] for g in recent]))
    return {
        "recentGames": recent,
        "seasonAvg": seasonAvg,
        "rollingAverages": {
            "last5Games": float(np.mean([g["statValue"] for g in recent[-5:]]))
        },
    }


def synth_opponent():
    return {
        "defensiveRating": float(random.uniform(95, 115)),
        "pace": float(random.uniform(90, 105)),
    }


def build_dataset(n_samples=200):
    # Attempt to build dataset from real historical data via training_data_service.
    # Define a small roster of players to pull seasons/games for (env override supported).
    players_env = os.environ.get("TOY_PLAYERS")
    players = (
        [p.strip() for p in players_env.split(",")] if players_env else ["LeBron James"]
    )
    season = os.environ.get("TOY_SEASON", "2024-25")
    stat = os.environ.get("TOY_STAT", "points")

    specs = []
    # For each player, fetch season games and produce (game_date, label) pairs
    for player in players:
        try:
            # Single call to retrieve season-scoped context
            ctx = nba_service.get_player_context_for_training(
                player, stat, game_date=season, season=season
            )
            recent = ctx.get("recentGamesRaw") or []
            # recent is expected newest-first; create samples where label is the next game's stat
            stat_field = "PTS" if stat.lower() in ("points", "pts") else stat.upper()
            for i in range(1, len(recent)):
                game = recent[i]
                prev_game = recent[i - 1]
                game_date = game.get("gameDate")
                label = prev_game.get(stat_field) or prev_game.get("statValue")
                if game_date and label is not None:
                    specs.append(
                        {
                            "player": player,
                            "stat": stat,
                            "game_date": game_date,
                            "season": season,
                            "label": label,
                        }
                    )
        except Exception:
            # skip player on error and continue building others
            continue

    X, y = training_data_service.build_dataset_from_specs(specs)
    feature_names = list(X.columns) if not X.empty else []
    # If no real samples found, fallback to synthetic dataset
    if X.empty:
        X_list = []
        y_list = []
        fe = FeatureEngineering()
        for _ in range(n_samples):
            pd = synth_player_data()
            od = synth_opponent()
            df = fe.engineer_features(pd, od)
            # target is next-game stat: simulate as last game value plus noise
            last = pd["recentGames"][-1]["statValue"]
            target = float(last + random.normalvariate(0, 2))
            X_list.append(df.iloc[0].values.astype(float))
            y_list.append(target)

        X = np.vstack(X_list)
        y = np.array(y_list)
        feature_names = list(df.columns)

    return X, y, feature_names


def main():
    random.seed(42)
    np.random.seed(42)

    print("Building dataset...")
    X, y, feature_names = build_dataset(300)
    print("Feature columns:", feature_names)
    print("Training RandomForest on engineered features...")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    # Save via ModelRegistry
    registry = ModelRegistry()
    player_name = os.environ.get("TOY_PLAYER_NAME", "LeBron James")
    version = "v1.real-features"
    notes = "RandomForest trained on FeatureEngineering outputs (synthetic dataset)"
    registry.save_model(player_name, model, version=version, notes=notes)

    out = {
        "player": player_name,
        "version": version,
        "model_path": os.path.abspath(registry._model_path(player_name)),
        "feature_count": len(feature_names),
        "feature_names": feature_names,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
