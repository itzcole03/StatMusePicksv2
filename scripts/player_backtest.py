"""Run per-player backtests using persisted models in `backend/models_store`.

This script loads each model file, generates synthetic feature rows compatible
with the model's expected feature dimensionality, obtains predictions, simulates
actual outcomes, and runs the BacktestEngine. Results are saved to
`backend/models_store/backtest_reports/player_backtest_<ts>.json`.
"""

import datetime
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
models_dir = repo_root / "backend" / "models_store"
out_dir = models_dir / "backtest_reports"
os.makedirs(out_dir, exist_ok=True)

from backend.evaluation.backtesting import BacktestEngine, write_report_json


def infer_n_features(model) -> int:
    # Try common sklearn attributes
    try:
        if hasattr(model, "n_features_in_"):
            return int(model.n_features_in_)
        if hasattr(model, "coef_"):
            coef = getattr(model, "coef_")
            try:
                return int(coef.shape[-1])
            except Exception:
                pass
        # VotingRegressor stores estimators_: try first estimator
        if hasattr(model, "estimators_") and getattr(model, "estimators_"):
            first = model.estimators_[0]
            return infer_n_features(first)
    except Exception:
        pass
    # fallback
    return 10


def make_synthetic_features(n_rows: int, n_cols: int):
    rng = np.random.RandomState(0)
    X = rng.normal(size=(n_rows, n_cols))
    cols = [f"f{i}" for i in range(n_cols)]
    return pd.DataFrame(X, columns=cols)


def process_model_file(path: Path):
    name = path.stem
    try:
        model = joblib.load(path)
    except Exception:
        return None

    n_feat = infer_n_features(model)
    dfX = make_synthetic_features(200, n_feat)

    # Try to predict; handle different model shapes
    try:
        raw = model.predict(dfX)
        preds = np.asarray(raw).ravel()
    except Exception:
        # try wrapping df.values
        try:
            raw = model.predict(dfX.values)
            preds = np.asarray(raw).ravel()
        except Exception:
            return None

    # market line as median prediction
    line = float(np.median(preds))
    # convert to probability via sigmoid
    probs = 1.0 / (1.0 + np.exp(-(preds - line)))

    # simulate actual outcomes from the model probabilities (for backtest)
    rng = np.random.RandomState(42)
    actuals = rng.binomial(1, probs)

    df = pd.DataFrame(
        {
            "pred_prob": probs,
            "actual": actuals,
            "odds": 1.909,
            "predicted_value": preds,
            "line": line,
        }
    )

    engine = BacktestEngine(start_bankroll=1000.0)
    res = engine.run(
        df,
        prob_col="pred_prob",
        actual_col="actual",
        odds_col="odds",
        stake_mode="flat",
        flat_stake=5.0,
    )

    summary = res._asdict() if hasattr(res, "_asdict") else res.__dict__
    return {"player": name, "n_rows": len(df), "n_features": n_feat, "summary": summary}


def main():
    out = []
    # consider only top-level model files ending with .pkl or .joblib
    for p in sorted(models_dir.iterdir()):
        if p.is_dir():
            continue
        if not (p.name.endswith(".pkl") or p.name.endswith(".joblib")):
            continue
        # skip meta or index files
        if p.name.endswith(".meta.json") or p.name.startswith("index"):
            continue
        try:
            r = process_model_file(p)
            if r is not None:
                out.append(r)
        except Exception:
            continue

    report = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
        "players_tested": len(out),
        "results": out,
    }

    fname = (
        out_dir
        / f'player_backtest_{datetime.datetime.now().strftime("%Y%m%dT%H%M%S")}.json'
    )
    write_report_json(report, str(fname))
    print("Wrote player backtest to", fname)


if __name__ == "__main__":
    main()
