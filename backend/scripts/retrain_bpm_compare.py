"""Train baseline vs BPM-enhanced models on synthetic data and report CV RMSE.

Saves models to `backend/models_store/` and writes a small CSV report.
"""
from __future__ import annotations
import os
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_squared_error
import joblib

from backend.services import training_pipeline as tp

OUT_DIR = os.path.join('backend', 'models_store')
os.makedirs(OUT_DIR, exist_ok=True)

def make_synthetic(n=300, include_bpm=False, seed=42):
    rng = np.random.RandomState(seed)
    recent_mean = rng.normal(12, 3, size=n)
    recent_std = np.abs(rng.normal(2, 0.8, size=n))
    multi_PER = rng.normal(15, 3, size=n)
    multi_TS = rng.normal(0.55, 0.04, size=n)
    multi_USG = rng.normal(22, 4, size=n)
    multi_season_pts = rng.normal(11, 3, size=n)
    multi_season_count = rng.randint(1,5,size=n)
    multi_PIE = rng.normal(0.1, 0.03, size=n)
    multi_off = rng.normal(110,5,size=n)
    multi_def = rng.normal(105,4,size=n)

    # BPM (when present) has modest predictive power
    if include_bpm:
        bpm = (multi_PER - 15.0) * 0.5 + rng.normal(0, 1.2, size=n)
    else:
        bpm = None

    # target: baseline depends on recent_mean, PER, and season pts; BPM if present
    target = (
        0.6 * recent_mean + 0.3 * (multi_PER - 15.0) + 0.2 * (multi_season_pts - 10.0)
        + rng.normal(0, 1.5, size=n)
    )
    if include_bpm:
        target = target + 0.4 * bpm

    data = {
        'recent_mean': recent_mean,
        'recent_std': recent_std,
        'multi_PER': multi_PER,
        'multi_TS_PCT': multi_TS,
        'multi_USG_PCT': multi_USG,
        'multi_season_PTS_avg': multi_season_pts,
        'multi_season_count': multi_season_count,
        'multi_PIE': multi_PIE,
        'multi_off_rating': multi_off,
        'multi_def_rating': multi_def,
        'target': target,
    }
    if include_bpm:
        data['multi_BPM'] = bpm

    return pd.DataFrame(data)


def build_estimator():
    # mimic training pipeline ensemble
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    en = ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42)
    est = VotingRegressor(estimators=[('rf', rf), ('elastic', en)], weights=[0.6,0.4])
    return est


def evaluate_df(df: pd.DataFrame, name: str):
    X = df.drop(columns=['target']).select_dtypes(include=[float, int]).fillna(0)
    y = df['target'].astype(float).values
    est = build_estimator()
    # 5-fold CV RMSE
    scores = cross_val_score(est, X, y, scoring='neg_mean_squared_error', cv=5)
    rmse = float(np.sqrt(-scores.mean()))
    # fit on full data and save
    est.fit(X, y)
    path = os.path.join(OUT_DIR, f"retrain_{name}.pkl")
    joblib.dump(est, path)
    return rmse, path


def main():
    # baseline (no BPM)
    df_base = make_synthetic(n=300, include_bpm=False, seed=1)
    rmse_base, path_base = evaluate_df(df_base, 'baseline')

    # with BPM feature
    df_bpm = make_synthetic(n=300, include_bpm=True, seed=2)
    rmse_bpm, path_bpm = evaluate_df(df_bpm, 'with_bpm')

    report = pd.DataFrame([
        {'experiment': 'baseline_no_BPM', 'rmse_cv': rmse_base, 'model_path': path_base},
        {'experiment': 'with_BPM', 'rmse_cv': rmse_bpm, 'model_path': path_bpm},
    ])
    report_path = os.path.join(OUT_DIR, 'retrain_bpm_report.csv')
    report.to_csv(report_path, index=False)

    # save a small JSON summary
    summary = {
        'baseline_rmse': rmse_base,
        'with_bpm_rmse': rmse_bpm,
        'report_csv': report_path,
        'models': [path_base, path_bpm],
    }
    with open(os.path.join(OUT_DIR, 'retrain_bpm_summary.json'), 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, indent=2)

    print('Done. Report:', report_path)
    print('Summary saved to backend/models_store/retrain_bpm_summary.json')

if __name__ == '__main__':
    main()
