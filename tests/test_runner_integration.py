import json
import os
from pathlib import Path

import pandas as pd

from backend.evaluation import run_backtest_with_metadata as runner


def make_training_csv(path: Path, n: int = 12, n_train: int | None = None, n_test: int | None = None):
    # create deterministic synthetic training data with required columns
    if n_train is None and n_test is None:
        # all rows will have the same split value ('train' to match earlier default)
        n_train = n
        n_test = 0
    elif n_train is None:
        n_train = max(0, n - int(n_test))
    elif n_test is None:
        n_test = max(0, n - int(n_train))

    dates = pd.date_range('2024-01-01', periods=n).strftime('%Y-%m-%d')
    players = [f'player_{i}' for i in range(n)]
    season_avg = list(range(10, 10 + n))
    last_3_std = [1.5] * n
    # target is season_avg plus a small offset
    target = [float(v) + (0.5 if i % 2 == 0 else -0.3) for i, v in enumerate(season_avg)]

    splits = ['train'] * n
    # mark last n_test rows as 'test'
    for i in range(n_test):
        splits[-1 - i] = 'test'

    df = pd.DataFrame({
        'game_date': dates,
        'player': players,
        'season_avg': season_avg,
        'last_3_std': last_3_std,
        'target': target,
        'split': splits,
    })
    df.to_csv(path, index=False)


def test_runner_writes_metadata_and_summary(tmp_path: Path):
    training_csv = tmp_path / 'train.csv'
    outdir = tmp_path / 'out'
    outdir.mkdir()
    # create 12 rows marked as 'test' so build_predictions selects them
    make_training_csv(training_csv, n=12, n_train=0, n_test=12)

    argv = ['--training-csv', str(training_csv), '--outdir', str(outdir), '--split', 'test', '--min-confidence', '0.0']
    runner.main(argv)

    # find created run folder
    runs = sorted([p for p in outdir.iterdir() if p.is_dir()])
    assert runs, 'No run directories created'
    last = runs[-1]

    meta_path = last / 'metadata.json'
    assert meta_path.exists(), 'metadata.json missing'
    with open(meta_path, 'r') as fh:
        meta = json.load(fh)
    assert 'training_csv' in meta
    assert meta.get('predictions_rows', 0) > 0

    summary_path = last / 'summary.csv'
    assert summary_path.exists()


def test_runner_isotonic_calibration(tmp_path: Path):
    training_csv = tmp_path / 'train_iso.csv'
    outdir = tmp_path / 'out_iso'
    outdir.mkdir()
    # create enough rows for calibration fitting
    # create enough rows where 20 are train (for calibration) and a few test rows for predictions
    make_training_csv(training_csv, n=23, n_train=20, n_test=3)

    argv = [
        '--training-csv', str(training_csv),
        '--outdir', str(outdir),
        '--split', 'test',
        '--isotonic',
        '--calibration-split', 'train',
        '--min-confidence', '0.0',
    ]
    runner.main(argv)

    runs = sorted([p for p in outdir.iterdir() if p.is_dir()])
    assert runs, 'No run directories created for isotonic test'
    last = runs[-1]

    meta_path = last / 'metadata.json'
    assert meta_path.exists()
    with open(meta_path, 'r') as fh:
        meta = json.load(fh)

    # isotonic calibration should be recorded in metadata
    assert meta.get('calibrated') is True
    cp = meta.get('calibration_params')
    assert cp is not None
    assert 'isotonic' in cp.get('method', '')
