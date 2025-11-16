import datetime
from pathlib import Path

import pandas as pd

from backend.evaluation import parameter_sweep as ps
from backend.evaluation.analysis import compare_calibration as cc


def test_small_sweep_creates_summary(tmp_path: Path):
    out_root = tmp_path / 'sweeps'
    out_root.mkdir()

    # tiny grid to keep runtime minimal
    line_shifts = [0.5]
    min_confidences = [0.1]
    decimal_odds = 1.9

    csv_path = ps.run_grid(line_shifts, min_confidences, decimal_odds)
    assert Path(csv_path).exists()
    df = pd.read_csv(csv_path)
    assert 'line_shift' in df.columns
    assert df.shape[0] >= 1


def test_produce_report_with_synthetic_results(tmp_path: Path):
    outdir = tmp_path / 'analysis' / datetime.datetime.now().strftime('test_%Y%m%dT%H%M%SZ')
    outdir.mkdir(parents=True)

    # create two synthetic result dicts mimicking run_and_collect output
    base_dir = tmp_path / 'run_base'
    base_dir.mkdir()
    # write a fake summary.csv for baseline
    sdf = pd.DataFrame([{'initial_bankroll': 1000.0, 'final_bankroll': 1100.0, 'roi': 0.1, 'win_rate': 0.5, 'total_bets': 10, 'sharpe': 0.2, 'max_drawdown': 0.1, 'cagr': 0.05}])
    sdf.to_csv(base_dir / 'summary.csv', index=False)

    cal_dir = tmp_path / 'run_cal'
    cal_dir.mkdir()
    # write a fake summary and calibration table
    sdf2 = pd.DataFrame([{'initial_bankroll': 1000.0, 'final_bankroll': 900.0, 'roi': -0.1, 'win_rate': 0.4, 'total_bets': 12, 'sharpe': -0.1, 'max_drawdown': 0.2, 'cagr': -0.02}])
    sdf2.to_csv(cal_dir / 'summary.csv', index=False)
    calib_df = pd.DataFrame({'_bin': [0, 1], 'mean_pred': [0.2, 0.8], 'mean_obs': [0.25, 0.75], 'count': [5, 5]})
    calib_df.to_csv(cal_dir / 'calibration.csv', index=False)

    results = [
        {'run_dir': str(base_dir), 'metadata': {}, 'summary': sdf.iloc[0].to_dict(), 'calibration': None},
        {'run_dir': str(cal_dir), 'metadata': {'calibration_params': {'method': 'isotonic'}}, 'summary': sdf2.iloc[0].to_dict(), 'calibration': calib_df},
    ]

    csv_path, md_path = cc.produce_report(results, outdir)
    assert csv_path.exists()
    assert md_path.exists()
    md_text = md_path.read_text(encoding='utf-8')
    assert 'Calibration Comparison Report' in md_text
    assert 'isotonic' in md_text.lower()
