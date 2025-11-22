import argparse
import json
import math
import logging
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
ROOT = Path(__file__).resolve().parents[1]


def find_manifest_in_datasets(root: Path) -> Path | None:
    # search for any dataset manifest under backend/data/datasets
    p = root / "backend" / "data" / "datasets"
    if not p.exists():
        return None
    for d in p.iterdir():
        if not d.is_dir():
            continue
        candidate = d / "dataset_manifest.json"
        if candidate.exists():
            return candidate
    return None


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", help="Path to dataset manifest.json (optional)")
    p.add_argument("--models-dir", help="Directory containing model .pkl files", default=str(ROOT / "backend" / "models_store" / "orchestrator_parallel"))
    p.add_argument("--report-json", help="Output JSON report path", default=str(ROOT / "backend" / "models_store" / "calibrator_report_parallel.json"))
    p.add_argument("--csv-out", help="Output CSV path", default=str(ROOT / "backend" / "models_store" / "calibration_metrics_parallel.csv"))
    return p.parse_args()


def ece_score(y_true, y_pred, n_bins=10):
    if len(y_pred) == 0:
        return None
    bins = np.linspace(np.min(y_pred), np.max(y_pred), n_bins + 1)
    ece = 0.0
    N = len(y_pred)
    # put values in bins (last bin inclusive)
    inds = np.digitize(y_pred, bins, right=False) - 1
    inds = np.clip(inds, 0, n_bins - 1)
    for b in range(n_bins):
        mask = inds == b
        nb = mask.sum()
        if nb == 0:
            continue
        pred_mean = y_pred[mask].mean()
        true_mean = y_true[mask].mean()
        ece += (nb / N) * abs(pred_mean - true_mean)
    return float(ece)


def metrics_for(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    if len(y_true) == 0:
        return None
    mse = float(np.mean((y_pred - y_true) ** 2))
    rmse = float(math.sqrt(mse))
    mae = float(np.mean(np.abs(y_pred - y_true)))
    brier = mse
    ece = ece_score(y_true, y_pred)
    return {"mse": mse, "rmse": rmse, "mae": mae, "brier": brier, "ece": ece}


def align_features(X, model):
    # try to reorder according to model.feature_names_in_ if available
    original_cols = list(X.columns)
    def _align_to_expected(expected):
        missing = [c for c in expected if c not in original_cols]
        extra = [c for c in original_cols if c not in expected]
        if missing:
            for c in missing:
                X[c] = 0.0
        # reindex will both reorder and drop extras
        X_aligned = X.reindex(columns=expected)
        # log any adjustments
        if missing or extra or expected != original_cols:
            logging.warning(
                "align_features adjusted columns: added=%s dropped=%s reordered_to=%s (model=%s)",
                missing, extra, expected[:10], getattr(model, '__class__', type(model)).__name__
            )
        return X_aligned

    if hasattr(model, 'feature_names_in_'):
        expected = list(model.feature_names_in_)
        return _align_to_expected(expected)

    # try estimator inside VotingRegressor
    if hasattr(model, 'estimators_') and len(model.estimators_)>0:
        est = model.estimators_[0]
        if hasattr(est, 'feature_names_in_'):
            expected = list(est.feature_names_in_)
            return _align_to_expected(expected)

    # fallback: keep numeric columns as-is
    numeric = X.select_dtypes(include=[np.number])
    if list(numeric.columns) != original_cols:
        logging.warning("align_features fallback to numeric columns; dropped non-numeric cols (model=%s)", getattr(model, '__class__', type(model)).__name__)
    return numeric


def main():
    args = parse_args()
    models_dir = Path(args.models_dir)
    report_json = Path(args.report_json)
    csv_out = Path(args.csv_out)

    manifest_path = None
    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            logging.warning("Provided manifest path %s does not exist; attempting to auto-discover", manifest_path)
            manifest_path = None

    if manifest_path is None:
        manifest_path = find_manifest_in_datasets(ROOT)

    if manifest_path is None:
        logging.info("No dataset manifest found; skipping compute_calibration_metrics (no val data).")
        return

    logging.info("Using manifest: %s", manifest_path)
    manifest = json.load(open(manifest_path))
    val_path = Path(manifest['parts']['val']['files']['features'])
    if not val_path.exists():
        logging.warning("Val features file %s not found; skipping.", val_path)
        return
    val_df = pd.read_parquet(val_path)
    report = []
    if report_json.exists():
        report = json.load(open(report_json))
        report_map = {r['player']: r for r in report}
    else:
        report_map = {}

    rows = []
    # iterate model files
    for pkl in models_dir.glob('*.pkl'):
        name = pkl.stem
        if name.endswith('_calibrator'):
            continue
        player = name.replace('_', ' ')
        model_path = models_dir / f"{name}.pkl"
        calib_path = models_dir / f"{name}_calibrator.pkl"
        try:
            model = joblib.load(model_path)
        except Exception as e:
            logging.exception("Failed to load model for %s: %s", player, e)
            continue
        calibrator = None
        if calib_path.exists():
            try:
                calibrator = joblib.load(calib_path)
            except Exception as e:
                logging.exception("Failed to load calibrator for %s: %s", player, e)
                calibrator = None
        # filter val
        dfp = val_df[val_df['player'] == player]
        if dfp.shape[0] < 3:
            logging.info("Not enough val rows for %s, skipping", player)
            continue
        y = dfp['target'].values
        X = dfp.drop(columns=['player', 'game_date', 'target'], errors='ignore')
        X = align_features(X, model)
        try:
            y_pred = model.predict(X)
        except Exception as e:
            # try to coerce to numpy array
            try:
                X2 = X.fillna(0.0).values
                y_pred = model.predict(X2)
            except Exception as e2:
                logging.exception("Prediction failed for %s: %s / %s", player, e, e2)
                continue
        before = metrics_for(y, y_pred)
        if calibrator is not None:
            try:
                y_after = calibrator.predict(y_pred)
            except Exception:
                try:
                    y_after = np.asarray([calibrator.transform(x) for x in y_pred])
                except Exception:
                    y_after = y_pred
        else:
            y_after = y_pred
        after = metrics_for(y, y_after)
        rows.append({
            'player': player,
            'mse_before': before['mse'] if before else None,
            'rmse_before': before['rmse'] if before else None,
            'mae_before': before['mae'] if before else None,
            'brier_before': before['brier'] if before else None,
            'ece_before': before['ece'] if before else None,
            'mse_after': after['mse'] if after else None,
            'rmse_after': after['rmse'] if after else None,
            'mae_after': after['mae'] if after else None,
            'brier_after': after['brier'] if after else None,
            'ece_after': after['ece'] if after else None,
            'status': 'computed'
        })
        # update report_map
        entry = report_map.get(player, {'player': player})
        entry['status'] = 'fitted' if calibrator is not None else 'no_calibrator'
        entry['metrics'] = {'player': player, 'method': ('isotonic' if calibrator is not None else 'raw'),
                            'before': before, 'after': after}
        report_map[player] = entry

    # write CSV
    df_out = pd.DataFrame(rows)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(csv_out, index=False)
    # write JSON
    out_list = list(report_map.values())
    report_json.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out_list, open(report_json, 'w'), indent=2)
    logging.info("Wrote metrics for %d players to %s", len(rows), csv_out)


if __name__ == '__main__':
    main()
