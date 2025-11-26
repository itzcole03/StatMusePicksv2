"""Evaluate blended ensemble of A/B models using optional per-player weights.

This script loads the test split from the dataset manifest and for each player
computes predictions from the A and B models (produced by `retrain_ab_selected.py`),
then blends predictions via weights and computes RMSE/MAE for the blended predictions.
If `backend/models_store/ensemble_weights_report.csv` exists and contains a
`player` and `best_weights` column, the script will attempt to parse per-player
weights (expects a python-list string like "[0.5,0.5]").
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.services.eval_report import load_model_if_exists

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ensemble_evaluation")


def safe_parse_weights(s: str) -> Optional[list]:
    try:
        w = ast.literal_eval(s)
        if isinstance(w, (list, tuple)):
            return [float(x) for x in w]
    except Exception:
        pass
    return None


def find_model_file(models_dir: Path, player: str, suffix: str):
    # look for <Player>_abA.pkl or <Player>_abB.pkl
    safe = player.replace(" ", "_")
    cand = models_dir / f"{safe}_{suffix}.pkl"
    if cand.exists():
        return str(cand)
    # fallback: glob
    for p in models_dir.glob(f"{safe}*{suffix}*.pkl"):
        return str(p)
    return None


def main(manifest: str, models_dir: str, out_csv: str = None):
    m = json.loads(Path(manifest).read_text(encoding="utf8"))
    test_p = Path(m["parts"]["test"]["files"]["features"])
    df_test = pd.read_parquet(test_p)
    players = sorted(df_test["player"].unique().tolist())

    models_dir = Path(models_dir)

    # load ensemble weights table if present
    weights_table = {}
    wpath = models_dir / "ensemble_weights_report.csv"
    if wpath.exists():
        try:
            wdf = pd.read_csv(wpath)
            for _, r in wdf.iterrows():
                if (
                    "player" in r
                    and "best_weights" in r
                    and pd.notna(r["best_weights"])
                ):
                    w = safe_parse_weights(r["best_weights"])
                    if w:
                        weights_table[r["player"]] = w
        except Exception:
            logger.exception("Failed to parse ensemble weights table")

    rows = []
    for player in players:
        player_df = df_test[df_test["player"] == player].copy()
        exclude = set(["game_date", "player", "target"])
        feature_cols = [c for c in player_df.columns if c not in exclude]
        if not feature_cols:
            rows.append({"player": player, "status": "no_features"})
            continue

        path_a = find_model_file(models_dir, player, "abA")
        path_b = find_model_file(models_dir, player, "abB")
        if not path_a or not path_b:
            rows.append(
                {
                    "player": player,
                    "status": "missing_models",
                    "path_a": path_a,
                    "path_b": path_b,
                }
            )
            continue

        m_a = load_model_if_exists(path_a)
        m_b = load_model_if_exists(path_b)
        if m_a is None or m_b is None:
            rows.append({"player": player, "status": "load_failed"})
            continue

        X = player_df[feature_cols].copy()

        def prepare_X_for_model(model, X_df):
            # If model stores feature names, align to them: add missing cols as 0, drop extras
            try:
                feat_names = getattr(model, "feature_names_in_", None)
                if feat_names is not None:
                    feat_names = [str(x) for x in feat_names]
                    Xp = X_df.copy()
                    for c in feat_names:
                        if c not in Xp.columns:
                            Xp[c] = 0.0
                    # keep only feat_names order
                    Xp = Xp.loc[:, feat_names]
                    return Xp.select_dtypes(include=[np.number]).fillna(0)
            except Exception:
                pass
            # fallback: numeric columns only
            return X_df.select_dtypes(include=[np.number]).fillna(0)

        X_for_a = prepare_X_for_model(m_a, X)
        X_for_b = prepare_X_for_model(m_b, X)

        preds_a = m_a.predict(X_for_a)
        preds_b = m_b.predict(X_for_b)

        # get weights
        w = weights_table.get(player, None)
        if not w or len(w) < 2:
            w = [0.5, 0.5]

        # blend only first two predictions
        blend = w[0] * preds_a + w[1] * preds_b

        y = player_df["target"].values.astype(float)
        rmse = float(np.sqrt(np.mean((blend - y) ** 2)))
        mae = float(np.mean(np.abs(blend - y)))

        rows.append(
            {
                "player": player,
                "status": "ok",
                "rmse": rmse,
                "mae": mae,
                "w_used": str(w),
            }
        )

    out_csv = out_csv or (models_dir / "ensemble_evaluation_report.csv")
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    logger.info("Wrote ensemble evaluation report to %s", out_csv)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--models-dir", default="backend/models_store")
    p.add_argument("--out-csv", default=None)
    args = p.parse_args()
    main(args.manifest, args.models_dir, args.out_csv)
