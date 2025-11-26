"""Retrain on existing dataset manifest with and without synthetic tracking features.

- Finds latest `dataset_manifest.json` under `backend/data/datasets`
- Loads train/val/test features (parquet)
- Adds synthetic tracking features correlated to `target`
- Trains two models (baseline, tracking)
- Evaluates RMSE on test set and runs basic backtest using BacktestEngine
- Writes report to `backend/models_store/backtest_reports/retrain_tracking_report_<ts>.json`
"""

import argparse
import datetime
import json
import logging
from datetime import timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "backend" / "models_store" / "backtest_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

import sys

sys.path.insert(0, str(ROOT))

from backend.evaluation.backtesting import BacktestEngine, write_report_json
from backend.services import training_pipeline as tp
from backend.services.model_registry import ModelRegistry

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def find_dataset_manifest():
    p = ROOT / "backend" / "data" / "datasets"
    for d in sorted(p.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        m = d / "dataset_manifest.json"
        if m.exists():
            return m
    return None


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def run(
    reuse_seed: int | None = 0, save_models: bool = False, outpath: str | None = None
):
    mpath = find_dataset_manifest()
    if mpath is None:
        raise SystemExit("No dataset manifest found under backend/data/datasets")
    manifest = json.load(open(mpath))
    parts = manifest.get("parts", {})
    train_path = Path(parts["train"]["files"]["features"])
    val_path = Path(parts["val"]["files"]["features"])
    test_path = Path(parts["test"]["files"]["features"])

    train_df = pd.read_parquet(train_path)
    val_df = pd.read_parquet(val_path)
    test_df = pd.read_parquet(test_path)

    # Build tracking features correlated with target (modest effect)
    def add_tracking(df):
        rng = np.random.RandomState(0)
        # trk speed m/s correlated to target noise
        trk_speed = 3.5 + 0.05 * df["target"] + rng.normal(0, 0.5, size=len(df))
        trk_dist = 4000 + 2.0 * df["target"] + rng.normal(0, 500, size=len(df))
        trk_touches = np.clip(
            8 + 0.2 * df["target"] + rng.normal(0, 2, size=len(df)), 0, None
        )
        trk_poss = 100 + 0.5 * df["target"] + rng.normal(0, 10, size=len(df))
        trk_xfg = np.clip(
            0.4 + 0.005 * df["target"] + rng.normal(0, 0.03, size=len(df)), 0, 1
        )
        df = df.copy()
        df["trk_avg_speed_mph"] = trk_speed * 2.23694
        df["trk_distance_miles_per_game"] = trk_dist / 1609.344
        df["trk_touches_per_game"] = trk_touches
        df["trk_time_possession_sec_per_game"] = trk_poss
        df["trk_exp_fg_pct"] = trk_xfg
        return df

    # Optionally set RNG seed for reproducibility
    if reuse_seed is not None:
        np.random.seed(int(reuse_seed))

    train_t = add_tracking(train_df)
    add_tracking(val_df)
    test_t = add_tracking(test_df)

    # Train baseline and tracking models (these may be heavier).
    model_b = tp.train_player_model(train_df, target_col="target")
    model_t = tp.train_player_model(train_t, target_col="target")

    # Optionally persist trained models via ModelRegistry
    if save_models:
        mr = ModelRegistry()
        try:
            mr.save_model(
                "retrain_baseline_tmp",
                model_b,
                version="v-dryrun",
                notes="baseline from retrain_roster_with_tracking",
            )
            mr.save_model(
                "retrain_tracking_tmp",
                model_t,
                version="v-dryrun",
                notes="tracking from retrain_roster_with_tracking",
            )
            log.info("Saved temporary models via ModelRegistry")
        except Exception:
            log.exception("Failed to save models via ModelRegistry")

    # Prepare X/test alignment
    def prepare_X(df_in):
        X = df_in.drop(columns=["target", "player", "game_date"], errors="ignore")
        X = X.select_dtypes(include=[np.number]).fillna(0)
        return X

    Xb_test = prepare_X(test_df)
    Xt_test = prepare_X(test_t)

    # Align columns
    def align(X_train, X_test):
        cols = list(X_train.columns)
        X = X_test.copy()
        for c in cols:
            if c not in X.columns:
                X[c] = 0.0
        X = X[cols]
        return X

    Xb_train = prepare_X(train_df)
    Xt_train = prepare_X(train_t)
    Xb_test_al = align(Xb_train, Xb_test)
    Xt_test_al = align(Xt_train, Xt_test)

    y_test = test_df["target"].values

    pred_b = model_b.predict(Xb_test_al)
    pred_t = model_t.predict(Xt_test_al)

    rmse_b = float(np.sqrt(((pred_b - y_test) ** 2).mean()))
    rmse_t = float(np.sqrt(((pred_t - y_test) ** 2).mean()))
    rmse_impr = (rmse_b - rmse_t) / rmse_b * 100.0 if rmse_b != 0 else 0.0

    # Convert preds to probabilities via sigmoid normalized by train target stats
    mean_train = train_df["target"].mean()
    std_train = train_df["target"].std() if train_df["target"].std() > 0 else 1.0
    prob_b = sigmoid((pred_b - mean_train) / std_train)
    prob_t = sigmoid((pred_t - mean_train) / std_train)

    # Build backtest records
    recs_b = [
        {"pred_prob": float(p), "actual": int(y > pred), "odds": 2.0}
        for p, y, pred in zip(prob_b, y_test, pred_b)
    ]
    recs_t = [
        {"pred_prob": float(p), "actual": int(y > pred), "odds": 2.0}
        for p, y, pred in zip(prob_t, y_test, pred_t)
    ]

    df_b = pd.DataFrame(recs_b)
    df_t = pd.DataFrame(recs_t)

    engine = BacktestEngine(start_bankroll=1000.0)
    res_b = engine.run(
        df_b,
        prob_col="pred_prob",
        actual_col="actual",
        odds_col="odds",
        stake_mode="flat",
        flat_stake=5.0,
    )
    res_t = engine.run(
        df_t,
        prob_col="pred_prob",
        actual_col="actual",
        odds_col="odds",
        stake_mode="flat",
        flat_stake=5.0,
    )

    report = {
        "generated_at": datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "dataset_manifest": str(mpath),
        "n_test_rows": int(len(test_df)),
        "rmse_baseline": rmse_b,
        "rmse_tracking": rmse_t,
        "rmse_improvement_pct": rmse_impr,
        "backtest_baseline": (
            res_b.__dict__ if hasattr(res_b, "__dict__") else dict(res_b)
        ),
        "backtest_tracking": (
            res_t.__dict__ if hasattr(res_t, "__dict__") else dict(res_t)
        ),
    }

    ts = datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outp = outpath or str(REPORT_DIR / f"retrain_tracking_report_{ts}.json")
    write_report_json(report, str(outp))
    log.info("Wrote report to %s", outp)
    print(json.dumps(report, indent=2))
    return report


def _cli():
    p = argparse.ArgumentParser(
        description="Retrain roster with synthetic tracking features (smoke)"
    )
    p.add_argument(
        "--seed", type=int, default=0, help="RNG seed for reproducibility (default: 0)"
    )
    p.add_argument(
        "--save-models",
        action="store_true",
        help="Persist temporary models to ModelRegistry",
    )
    p.add_argument(
        "--out",
        type=str,
        help="Output report path; defaults to models_store/backtest_reports",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not persist models; only run training and reports",
    )
    args = p.parse_args()
    try:
        run(
            reuse_seed=args.seed,
            save_models=args.save_models and not args.dry_run,
            outpath=args.out,
        )
    except SystemExit:
        raise
    except Exception:
        log.exception("Retrain failed")
        raise


if __name__ == "__main__":
    _cli()
