"""Retrain A/B using per-player selected features.

This script reads `backend/models_store/feature_selection_report.csv` to
discover selected features per player, then for each player it trains two
models:
 - A: includes LLM-derived features
 - B: excludes LLM-derived features

By default the script limits to a small number of players for smoke runs.
"""

from __future__ import annotations

import argparse
import ast
import logging
from pathlib import Path
from typing import List

import pandas as pd

from backend.services import training_data_service, training_pipeline
from backend.services.llm_feature_service import create_default_service

logger = logging.getLogger("retrain_ab_selected")
logging.basicConfig(level=logging.INFO)


def parse_list_field(val):
    if pd.isna(val):
        return []
    if isinstance(val, (list, tuple, set)):
        return list(val)
    s = str(val).strip()
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, (list, tuple, set)):
            return [str(x).strip() for x in parsed]
    except Exception:
        pass
    if "," in s:
        return [p.strip() for p in s.split(",") if p.strip()]
    if ";" in s:
        return [p.strip() for p in s.split(";") if p.strip()]
    if s == "[]" or s == "":
        return []
    return [s]


def augment_with_llm(df: pd.DataFrame, player_name: str):
    llm = create_default_service()

    def text_fetcher(name: str) -> str:
        return ""

    try:
        feats = llm.fetch_news_and_extract(player_name, "news_v1", text_fetcher)
    except Exception:
        logger.exception("LLM feature extraction failed for %s", player_name)
        feats = {"injury_sentiment": 0.0, "morale_score": 0.0, "motivation": 0.0}

    df = df.copy()
    df["injury_sentiment"] = float(feats.get("injury_sentiment") or 0.0)
    df["morale_score"] = float(feats.get("morale_score") or 0.0)
    df["motivation"] = float(feats.get("motivation") or 0.0)
    return df


def train_player_pair(
    player: str,
    selected_features: List[str],
    min_games: int,
    seasons: List[str],
    out_dir: Path,
):
    try:
        df = training_data_service.generate_training_data(
            player, min_games=min_games, fetch_limit=300, seasons=seasons
        )
    except Exception:
        logger.exception("Failed to generate training data for %s", player)
        return None

    # ensure target present
    if "target" not in df.columns:
        logger.warning("No target column for %s, skipping", player)
        return None

    # intersect selected features with available cols
    feats = [f for f in selected_features if f in df.columns]
    if not feats:
        logger.warning(
            "No selected features present for %s (available cols: %s)",
            player,
            list(df.columns[:10]),
        )
        return None

    cols = feats + ["target"]
    df_sub = df[cols].copy()

    # Train A (with LLM)
    try:
        df_a = augment_with_llm(df_sub, player)
        model_a = training_pipeline.train_player_model(df_a, target_col="target")
        out_a = out_dir / f"{player.replace(' ', '_')}_abA.pkl"
        training_pipeline.save_model(model_a, str(out_a))
        logger.info("Saved A model for %s -> %s", player, out_a)
    except Exception:
        logger.exception("Failed training A for %s", player)

    # Train B (no LLM)
    try:
        df_b = df_sub.copy()
        model_b = training_pipeline.train_player_model(df_b, target_col="target")
        out_b = out_dir / f"{player.replace(' ', '_')}_abB.pkl"
        training_pipeline.save_model(model_b, str(out_b))
        logger.info("Saved B model for %s -> %s", player, out_b)
    except Exception:
        logger.exception("Failed training B for %s", player)


def compute_last3_seasons():
    import datetime

    now = datetime.date.today()
    year = now.year
    if now.month >= 10:
        start_year = year
    else:
        start_year = year - 1
    seasons = [
        f"{start_year - i}-{str((start_year - i + 1)%100).zfill(2)}"
        for i in range(0, 3)
    ]
    return seasons


def main(
    limit: int = 20,
    min_games: int = 5,
    report_path: str | None = None,
    out_dir: str | None = None,
):
    repo_root = Path(__file__).resolve().parents[2]
    report_path = (
        Path(report_path)
        if report_path
        else repo_root / "backend/models_store/feature_selection_report.csv"
    )
    out_dir = Path(out_dir) if out_dir else repo_root / "backend/models_store"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not report_path.exists():
        logger.error("Feature selection report not found: %s", report_path)
        return 2

    df = pd.read_csv(report_path)
    # prefer players with status 'ok'
    df_ok = df[df["status"] == "ok"] if "status" in df.columns else df
    players = df_ok["player"].tolist()
    if limit:
        players = players[:limit]

    seasons = compute_last3_seasons()

    for p in players:
        row = df[df["player"] == p].iloc[0]
        rfe = parse_list_field(row.get("rfe_selected", ""))
        corr = parse_list_field(row.get("corr_selected", ""))
        selected = rfe if rfe else corr
        if not selected:
            logger.info("No selected features for %s, skipping", p)
            continue
        logger.info("Training A/B for %s with %d features", p, len(selected))
        train_player_pair(p, selected, min_games, seasons, out_dir)

    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--min-games", type=int, default=5)
    p.add_argument("--report", default=None)
    p.add_argument("--out-dir", default=None)
    args = p.parse_args()
    raise SystemExit(main(args.limit, args.min_games, args.report, args.out_dir))
