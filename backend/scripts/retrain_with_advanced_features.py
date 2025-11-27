"""Retrain small roster using advanced and LLM-derived features (smoke run).

This script is intended for local development: it fetches per-player
training rows via `training_data_service.generate_training_data`, augments
each player's rows with deterministic LLM features from
`backend.services.llm_feature_service`, trains a model using
`backend.services.training_pipeline.train_player_model`, and saves the
artifact under `backend/models_store/`.

The script is defensive: when external data sources are unavailable it will
skip players rather than failing the entire run.
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import List

import pandas as pd

from backend.services import nba_stats_client, training_data_service, training_pipeline
from backend.services.llm_feature_service import create_default_service

logger = logging.getLogger("retrain_with_advanced_features")
logging.basicConfig(level=logging.INFO)


def augment_with_llm(df: pd.DataFrame, player_name: str):
    """Add deterministic LLM-derived features for all rows of `df` for player."""
    llm = create_default_service()

    def text_fetcher(name: str) -> str:
        # Best-effort: no external news fetcher available here; return empty
        # so the LLM service's deterministic placeholder is used.
        return ""

    try:
        feats = llm.fetch_news_and_extract(player_name, "news_v1", text_fetcher)
    except Exception:
        logger.exception("LLM feature extraction failed for %s", player_name)
        feats = {"injury_sentiment": 0.0, "morale_score": 0.0, "motivation": 0.0}

    # Ensure columns exist with floats
    df = df.copy()
    df["injury_sentiment"] = float(feats.get("injury_sentiment") or 0.0)
    df["morale_score"] = float(feats.get("morale_score") or 0.0)
    df["motivation"] = float(feats.get("motivation") or 0.0)
    return df


def train_and_save(player: str, output_dir: str = "backend/models_store") -> str:
    try:
        # allow overriding min_games for smoke runs via env var
        min_games = int(os.environ.get("TRAIN_MIN_GAMES_OVERRIDE", "10"))
        # prefer recent seasons (last 3) when retraining across roster
        seasons = os.environ.get("TRAIN_SEASONS_OVERRIDE")
        if seasons:
            seasons = [s.strip() for s in seasons.split(",") if s.strip()]
        else:
            # compute last 3 seasons like '2023-24'
            import datetime

            now = datetime.date.today()
            year = now.year
            # determine current NBA season by month (season starts in Oct)
            if now.month >= 10:
                start_year = year
            else:
                start_year = year - 1
            seasons = []
            for i in range(0, 3):
                y = start_year - i
                seasons.append(f"{y}-{str((y+1)%100).zfill(2)}")

        df = training_data_service.generate_training_data(
            player, min_games=min_games, fetch_limit=300, seasons=seasons
        )
    except Exception:
        logger.exception("Failed to generate training data for %s", player)
        raise

    df_aug = augment_with_llm(df, player)

    # The training pipeline expects the target column named 'target'
    try:
        model = training_pipeline.train_player_model(df_aug, target_col="target")
    except Exception:
        logger.exception("Training failed for %s", player)
        raise

    os.makedirs(output_dir, exist_ok=True)
    safe_name = player.replace(" ", "_")
    out_path = os.path.join(output_dir, f"{safe_name}_advanced.pkl")
    try:
        training_pipeline.save_model(model, out_path)
    except Exception:
        logger.exception("Failed to save model for %s", player)
        raise

    return out_path


def main(players: List[str]):
    saved = []
    for p in players:
        logger.info("Processing player: %s", p)
        try:
            path = train_and_save(p)
            logger.info("Saved model for %s -> %s", p, path)
            saved.append((p, path))
        except Exception:
            logger.exception("Skipping player due to error: %s", p)
            continue

    if saved:
        logger.info("Completed training for %d players", len(saved))
    else:
        logger.warning("No models saved; check logs for failures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Retrain small roster with advanced + LLM features (smoke)"
    )
    parser.add_argument(
        "--players",
        help="Comma-separated player list (defaults to full NBA roster)",
        default=None,
    )
    parser.add_argument(
        "--min-games",
        type=int,
        default=5,
        help="Minimum games required to generate training data",
    )
    args = parser.parse_args()

    if args.players:
        players = [p.strip() for p in args.players.split(",") if p.strip()]
    else:
        # Attempt to fetch full NBA roster via nba_stats_client.fetch_all_players()
        try:
            allp = nba_stats_client.fetch_all_players() or []
            players = []
            for p in allp:
                # prefer likely-active/current players to avoid scanning historical rosters
                name = (
                    p.get("full_name")
                    or p.get("fullName")
                    or p.get("display_name")
                    or p.get("displayName")
                )
                if not name:
                    continue
                is_active = False
                for k in ("is_active", "isActive", "active", "is_current"):
                    if k in p and p.get(k):
                        is_active = True
                        break
                # many nba_api entries include team/teamId when current
                if not is_active:
                    for k in ("teamId", "team", "teamIdCurrent", "teamIdCurrent"):
                        if k in p and p.get(k):
                            is_active = True
                            break
                if is_active:
                    players.append(name)
            # fall back to some recent players if filter produced empty list
            if not players:
                for p in allp[:200]:
                    name = (
                        p.get("full_name")
                        or p.get("fullName")
                        or p.get("display_name")
                        or p.get("displayName")
                    )
                    if name:
                        players.append(name)
        except Exception:
            # fall back to a small default roster if fetch fails
            players = [
                "LeBron James",
                "Stephen Curry",
                "Luka Doncic",
                "Kevin Durant",
                "Jayson Tatum",
            ]

    # respect requested min_games when calling training_data_service
    # create a small wrapper to pass the value through via environment variable
    # (simple approach to avoid changing too many function signatures)
    os.environ["TRAIN_MIN_GAMES_OVERRIDE"] = str(args.min_games)

    # Also set seasons override env so train_and_save uses same seasons when spawning
    # (keeps behavior consistent if run in parallel contexts)
    # compute last 3 seasons
    import datetime

    now = datetime.date.today()
    year = now.year
    if now.month >= 10:
        start_year = year
    else:
        start_year = year - 1
    seasons_list = [
        f"{start_year - i}-{str((start_year - i + 1)%100).zfill(2)}"
        for i in range(0, 3)
    ]
    os.environ["TRAIN_SEASONS_OVERRIDE"] = ",".join(seasons_list)

    # adapt training_data_service call by monkeypatching a small helper if present
    try:
        # If the service reads environ overrides we'll handle below; else the script
        # will still pass min_games directly via train_and_save's call.
        pass
    except Exception:
        pass

    # run main
    main(players)
