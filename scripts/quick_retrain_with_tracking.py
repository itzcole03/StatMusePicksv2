"""Quick retrain + comparison script (baseline vs tracking features).

Creates a synthetic chronological dataset for one player, with and without
tracking features. Trains VotingRegressor ensembles and compares test RMSE.
Writes a small JSON report under `backend/models_store/backtest_reports/`.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from backend.services import training_data_service as tds
from backend.services import training_pipeline as tp

OUT_DIR = os.path.join("backend", "models_store", "backtest_reports")
os.makedirs(OUT_DIR, exist_ok=True)

PLAYER = "Synthetic Player"
N = 300
np.random.seed(0)

# chronological dates oldest -> newest
start = datetime(2023, 10, 1)
dates = [start + timedelta(days=i * 2) for i in range(N)]

# base features
last_3 = np.clip(np.random.normal(loc=20, scale=5, size=N), 0, None)
last_5 = last_3 + np.random.normal(0, 1, N)
last_10 = last_3 + np.random.normal(0, 2, N)
days_rest = np.random.choice([0, 1, 2, 3, 4], size=N, p=[0.1, 0.4, 0.3, 0.15, 0.05])
is_home = np.random.choice([0, 1], size=N)
opp_def = np.random.normal(110, 5, size=N)

# Tracking signal (introduce modest correlation to target)
trk_speed = np.clip(np.random.normal(4.5, 0.6, size=N), 0, None)  # m/s-like
trk_distance = np.clip(np.random.normal(5000, 800, size=N), 0, None)  # meters
trk_touches = np.clip(np.random.poisson(10, size=N), 0, None)
trk_poss = np.clip(np.random.normal(120, 30, size=N), 0, None)  # seconds
trk_xfg = np.clip(np.random.normal(0.45, 0.06, size=N), 0, 1)

# True underlying stat (target): depends mostly on last_5 but with small tracking effect
noise = np.random.normal(0, 3.0, size=N)
true_stat = (
    0.6 * last_5 + 0.2 * last_3 + 0.1 * (trk_xfg * 10) + 0.05 * (trk_touches) + noise
)

# Build DataFrame
df = pd.DataFrame(
    {
        "player": [PLAYER] * N,
        "game_date": dates,
        "last_3_avg": last_3,
        "last_5_avg": last_5,
        "last_10_avg": last_10,
        "days_rest": days_rest,
        "is_home": is_home,
        "opp_def": opp_def,
        # tracking (original units)
        "trk_avg_speed_m_s": trk_speed,
        "trk_distance_m": trk_distance,
        "trk_touches": trk_touches,
        "trk_time_poss_sec": trk_poss,
        "trk_exp_fg_pct": trk_xfg,
        "target": true_stat,
    }
)

# Create baseline (drop tracking columns) and tracking variant (convert tracking to numeric features used by pipeline)
baseline = df.copy().drop(
    columns=[
        "trk_avg_speed_m_s",
        "trk_distance_m",
        "trk_touches",
        "trk_time_poss_sec",
        "trk_exp_fg_pct",
    ]
)
tracking = df.copy()
# normalize tracking to feature names the pipeline expects (convert m/s->mph, m->miles)
tracking["trk_avg_speed_mph"] = tracking["trk_avg_speed_m_s"] * 2.23694
tracking["trk_distance_miles_per_game"] = tracking["trk_distance_m"] / 1609.344
tracking["trk_touches_per_game"] = tracking["trk_touches"]
tracking["trk_time_possession_sec_per_game"] = tracking["trk_time_poss_sec"]
tracking["trk_exp_fg_pct"] = tracking["trk_exp_fg_pct"]

# Ensure chronological split helper available
train_b, val_b, test_b = tds.chronological_split_by_ratio(
    baseline, date_col="game_date", train_frac=0.7, val_frac=0.15, test_frac=0.15
)
train_t, val_t, test_t = tds.chronological_split_by_ratio(
    tracking, date_col="game_date", train_frac=0.7, val_frac=0.15, test_frac=0.15
)

# Train models
model_b = tp.train_player_model(train_b, target_col="target")
model_t = tp.train_player_model(train_t, target_col="target")


# Prepare numeric feature matrices for test
def prepare_X(df_in):
    X = df_in.drop(columns=["target", "player", "game_date"], errors="ignore")
    # keep numeric columns; but preserve any existing columns (we'll coerce later)
    X = X.select_dtypes(include=[float, int, "number"]).copy()
    X = X.fillna(0)
    return X


Xb_test = prepare_X(test_b)
yb_test = test_b["target"].values
yt_test = test_t["target"].values


# Predict and compute RMSE
# Align test feature columns to training feature set used during fit
def align_features(X_train_df, X_test_df):
    train_cols = list(X_train_df.columns)
    X = X_test_df.copy()
    for c in train_cols:
        if c not in X.columns:
            X[c] = 0.0
    # drop any extra cols not seen during training
    X = X[train_cols]
    return X


Xb_test = prepare_X(test_b)
yb_test = test_b["target"].values
Xt_test = prepare_X(test_t)


# Build X_train frames used during fit to extract feature schema
Xb_train = prepare_X(train_b)
Xt_train = prepare_X(train_t)

# Align test sets
Xb_test_al = align_features(Xb_train, Xb_test)
Xt_test_al = align_features(Xt_train, Xt_test)

# Predict and compute RMSE
pred_b = model_b.predict(Xb_test_al)
pred_t = model_t.predict(Xt_test_al)

rmse_b = float(np.sqrt(((pred_b - yb_test) ** 2).mean()))
rmse_t = float(np.sqrt(((pred_t - yt_test) ** 2).mean()))
impr = (rmse_b - rmse_t) / rmse_b * 100.0 if rmse_b != 0 else 0.0
report = {
    "player": PLAYER,
    "rows": int(len(df)),
    "train_rows": int(len(train_b)),
    "val_rows": int(len(val_b)),
    "test_rows": int(len(test_b)),
    "rmse_baseline": rmse_b,
    "rmse_tracking": rmse_t,
    "rmse_improvement_pct": impr,
}

ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out_path = os.path.join(OUT_DIR, f"tracking_impact_report_{ts}.json")
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2)

print("Wrote report to", out_path)
print(json.dumps(report, indent=2))

# Exit with success
