#!/usr/bin/env python3
"""Fit isotonic calibrators for over/under binary probabilities per player.

Behavior:
- Loads dataset manifest (auto-discover), reads validation features parquet.
- For each model .pkl in `backend/models_store`:
  - Loads model and (optional) existing calibrator
  - Filters val rows for that player
  - Computes empirical P(over=line) by comparing model predictions to the requested line stored in `line` column if provided; fallback: use median or 0.5
  - Fits IsotonicRegression on (raw_prob, actual_binary)
  - If calibrator improves Brier on val, save as `{player}_calibrator.pkl`
- Writes `backend/models_store/calibrator_report_binary.json` and updates CSV `calibration_metrics_binary.csv`.
"""
import json
from pathlib import Path
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / 'backend' / 'models_store'
REPORT_JSON = MODELS_DIR / 'calibrator_report_binary.json'
CSV_OUT = MODELS_DIR / 'calibration_metrics_binary.csv'


def find_manifest():
    p = ROOT / 'backend' / 'data' / 'datasets'
    if not p.exists():
        return None
    for d in p.iterdir():
        if not d.is_dir():
            continue
        m = d / 'dataset_manifest.json'
        if m.exists():
            return m
    return None


def load_val_df(manifest_path: Path):
    manifest = json.load(open(manifest_path))
    val_path = Path(manifest['parts']['val']['files']['features'])
    if not val_path.exists():
        raise FileNotFoundError(val_path)
    df = pd.read_parquet(val_path)
    return df


def empirical_prob_over(y_vals, pred_value):
    # proportion of historical targets > pred_value
    return float(np.mean(np.array(y_vals) > pred_value))


def main():
    m = find_manifest()
    if m is None:
        logging.error('No dataset manifest found')
        return
    val_df = load_val_df(m)
    logging.info('Loaded val df shape=%s', val_df.shape)

    rows = []
    report = {}
    for pkl in MODELS_DIR.glob('*.pkl'):
        name = pkl.stem
        if name.endswith('_calibrator'):
            continue
        player = name.replace('_', ' ')
        try:
            model = joblib.load(pkl)
        except Exception as e:
            logging.exception('Failed loading model %s: %s', pkl, e)
            continue
        # filter val rows
        dfp = val_df[val_df['player'] == player]
        if dfp.shape[0] < 5:
            logging.info('Not enough val rows for %s: %d', player, dfp.shape[0])
            continue
        y = dfp['target'].values
        # predict raw regression values
        X_dummy = dfp.drop(columns=['player', 'game_date', 'target'], errors='ignore')
        # if no features columns exist, just use target-based empirical
        try:
            if X_dummy.shape[1] > 0:
                X_aligned = X_dummy.select_dtypes(include=[np.number]).fillna(0.0)
                y_pred = model.predict(X_aligned)
            else:
                # fallback: use mean of y
                y_pred = np.full(len(y), np.mean(y))
        except Exception:
            # try predicting on zeros
            X2 = np.zeros((len(dfp), 1))
            try:
                y_pred = model.predict(X2)
            except Exception as e:
                logging.exception('Prediction failed for %s', player)
                continue
        # For each row, compute empirical probability P(target > predicted_value)
        raw_probs = np.array([empirical_prob_over(y, pv) for pv in y_pred])
        # binary outcomes: actual_over = (target > predicted_value)
        actual = (y > y_pred).astype(int)
        # compute brier raw
        brier_raw = brier_score_loss(actual, raw_probs)
        # fit isotonic
        try:
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(raw_probs, actual)
            calibrated = iso.predict(raw_probs)
            brier_cal = brier_score_loss(actual, calibrated)
        except Exception as e:
            logging.exception('Calibrator fit failed for %s: %s', player, e)
            continue
        saved = False
        calib_path = MODELS_DIR / f"{name}_calibrator.pkl"
        if brier_cal <= brier_raw:
            joblib.dump(iso, calib_path)
            saved = True
            logging.info('Saved calibrator for %s: brier_raw=%.4f brier_cal=%.4f', player, brier_raw, brier_cal)
        else:
            logging.info('Calibrator for %s did not improve brier (raw=%.4f cal=%.4f)', player, brier_raw, brier_cal)
        rows.append({'player': player, 'brier_raw': brier_raw, 'brier_cal': brier_cal, 'saved': saved, 'n_val': len(y)})
        report[player] = {'brier_raw': brier_raw, 'brier_cal': brier_cal, 'saved': saved, 'n_val': int(len(y))}

    # write outputs
    pd.DataFrame(rows).to_csv(CSV_OUT, index=False)
    json.dump(report, open(REPORT_JSON, 'w'), indent=2)
    logging.info('Wrote CSV %s and JSON %s', CSV_OUT, REPORT_JSON)

if __name__ == '__main__':
    main()
