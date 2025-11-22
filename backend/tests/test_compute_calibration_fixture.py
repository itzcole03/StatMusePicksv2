import sys
import subprocess
import json
from pathlib import Path

import pandas as pd
import numpy as np
import joblib

def test_compute_metrics_on_fixture(tmp_path):
    ROOT = Path.cwd()
    fx = ROOT / 'backend' / 'tests' / 'fixtures' / 'calib'
    fx.mkdir(parents=True, exist_ok=True)

    # create val dataframe
    dates = pd.date_range(start='2020-01-01', periods=6, freq='D')
    df = pd.DataFrame({
        'player': ['Fixture Player']*6,
        'game_date': dates,
        'target': [1,2,1,2,1,2],
        'lag_1': [0.5,1.0,2.0,1.0,2.0,1.0],
        'lag_3_mean': [0.5,0.7,0.8,0.9,1.0,1.1],
    })
    val_path = fx / 'val_features.parquet'
    df.to_parquet(val_path)

    # manifest
    manifest = {'parts': {'val': {'files': {'features': str(val_path)}}}}
    manifest_path = fx / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest))

    # train a simple model and save
    models_dir = fx / 'models'
    models_dir.mkdir(parents=True, exist_ok=True)
    X = df[['lag_1','lag_3_mean']]
    y = df['target']
    from sklearn.ensemble import RandomForestRegressor
    model = RandomForestRegressor(n_estimators=10, random_state=0)
    model.fit(X, y)
    joblib.dump(model, str(models_dir / 'Fixture_Player.pkl'))

    # run compute script
    cmd = [sys.executable, 'scripts/compute_calibration_metrics.py',
           '--manifest', str(manifest_path),
           '--models-dir', str(models_dir),
           '--report-json', str(fx / 'calibrator_report.json'),
           '--csv-out', str(fx / 'calibration_metrics.csv')]

    subprocess.run(cmd, check=True)

    csv_file = fx / 'calibration_metrics.csv'
    json_file = fx / 'calibrator_report.json'
    assert csv_file.exists(), 'Expected calibration CSV to be created'
    df_out = pd.read_csv(csv_file)
    assert len(df_out) >= 1, 'Expected at least one metrics row in CSV'
    assert json_file.exists(), 'Expected calibrator JSON report to be created'
