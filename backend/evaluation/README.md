# Backend Evaluation tools

This directory contains scripts to run backtests and perform parameter sweeps.

Usage examples:

Run a reproducible backtest (no calibration):

```pwsh
$env:PYTHONPATH='C:\path\to\repo'; & .\.venv\Scripts\python.exe backend/evaluation/run_backtest_with_metadata.py --line-shift 1.5 --decimal-odds 2.2 --min-confidence 0.25
```

Run a reproducible backtest with Platt-scaling calibration (fits on `train` split):

```pwsh
$env:PYTHONPATH='C:\path\to\repo'; & .\.venv\Scripts\python.exe backend/evaluation/run_backtest_with_metadata.py --line-shift 1.5 --decimal-odds 2.2 --min-confidence 0.25 --calibrate --calibration-split train
```

Create a predictions+actuals pair from a training CSV:

```pwsh
$env:PYTHONPATH='C:\path\to\repo'; & .\.venv\Scripts\python.exe backend/evaluation/convert_training_to_predictions.py --training-csv backend/data/training_datasets/points_dataset_174f1d9ac88b.csv --outdir backend/evaluation/backtest_reports/inputs_from_training --line-shift 1.5 --decimal-odds 2.2
```

Run a parameter sweep (quick scan):

```pwsh
$env:PYTHONPATH='C:\path\to\repo'; & .\.venv\Scripts\python.exe backend/evaluation/parameter_sweep.py
```

Compare calibrated vs uncalibrated runs for a representative parameter set:

```pwsh
$env:PYTHONPATH='C:\path\to\repo'; & .\.venv\Scripts\python.exe backend/evaluation/analysis/compare_calibration.py
```

Notes
- Scripts assume you run them from the repository root and that `.venv` is activated or accessible.
- All runs write metadata and reports under `backend/evaluation/backtest_reports/` for reproducibility.
# Backtesting (backend/evaluation)

This folder contains a lightweight backtesting engine and test fixtures used for
local experimentation and CI smoke tests.

Key behaviors:
- Accepts prediction CSVs with `game_date`, `player`, `over_probability`, `confidence`, and optional `decimal_odds` or `odds` columns.
- If `decimal_odds` is not provided it defaults to `2.0` (even money).
- If `expected_value` is not supplied, the engine computes per-unit EV from probability and odds:
  EV_per_unit = (odds - 1) * p - (1 - p)
- Stake sizing uses a generalized Kelly formula for decimal odds and applies a per-bet cap via `max_fraction_per_bet` (default 0.02).
- Payouts are modeled using decimal odds: profit = stake * (odds - 1) on wins, -stake on losses.

Quick CLI usage:

```pwsh
python backend/evaluation/backtesting.py \
  --predictions backend/evaluation/fixtures/predictions_sample.csv \
  --actuals backend/evaluation/fixtures/actuals_sample.csv \
  --outdir backend/evaluation/backtest_reports
```

Notes:
- The engine is intentionally simple for reproducible CI smoke-runs. For production/backtests against market lines, consider adjusting for vig/market-implied probabilities and richer stake-sizing logic.
- See `backend/tests/test_backtesting.py` for unit test examples covering ROI, Sharpe, multiple bets, and stake-capping.
# Evaluation / Calibration Metrics

This folder provides lightweight calibration metrics used by the backend:

- `brier_score(y_true, y_prob)` — mean squared error between predicted probability and outcome.
- `expected_calibration_error(y_true, y_prob, n_bins=10)` — ECE using equal-width bins.
- `reliability_diagram(y_true, y_prob, n_bins=10, ax=None)` — plot a reliability diagram (requires `matplotlib`).

Usage examples:

```python
from backend.evaluation import calibration_metrics as cm
import numpy as np

n = 1000
rng = np.random.RandomState(0)
true_prob = rng.uniform(0.1, 0.9, size=n)
y = rng.binomial(1, true_prob)
pred = true_prob * 0.9 + 0.05  # slightly biased

print('Brier:', cm.brier_score(y, pred))
print('ECE:', cm.expected_calibration_error(y, pred, n_bins=10))

# To plot (optional):
try:
    fig, ax = cm.reliability_diagram(y, pred, n_bins=10)
    fig.savefig('reliability_diagram.png')
    print('Saved reliability_diagram.png')
except RuntimeError:
    print('matplotlib not available; skipping plot')
```

The `example_usage.py` script in the same folder provides a runnable demonstration.
