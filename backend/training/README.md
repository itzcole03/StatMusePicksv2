# Training script — backend/training/train_models.py

This document describes the small per-player training script used for local development and CI.

Usage
-----

Run from the repository root (recommended) so package imports resolve:

```powershell
& .\.venv\Scripts\Activate.ps1
python -m backend.training.train_models --dataset <path/to/dataset.csv> --store-dir backend/models_store --min-games 50 --trials 50 --report training_report.csv --verbose
```

Key arguments
- `--dataset` (required): CSV or parquet file produced by the data ingest pipeline. Must contain `player_id`, `target`, and feature columns.
- `--store-dir`: Directory to write model artifacts (default `backend/models_store`).
- `--min-games`: Minimum rows per player required to attempt training (default `50` in production; use lower values for local smoke testing).
- `--trials`: Number of Optuna trials per estimator on the classification path (default `50`).
- `--report`: Optional CSV file to append per-player training summary rows.
- `--verbose`: enable debug logging.

Behavior notes
- The script trains models per `player_id`. For binary classification targets it attempts RandomForest, XGBoost (if installed), and ElasticNet (logistic) — each tuned with Optuna (Brier score).
- If players have insufficient diversity in labels (single-class across union training folds), the script will skip classifier training for that player and register a mean-baseline model instead. This is intentional to avoid training degenerate classifiers.
- For regression targets the script runs an Optuna search using a brier-like proxy on regression outputs.
- The script saves artifacts via `backend.services.model_registry.PlayerModelRegistry` — artifacts are written as `{player_safe}_v{version}.joblib` and indexed in `index.json` inside `--store-dir`.

Testing
- The repo includes `tests/test_train_models.py` (pytest). When running tests locally ensure `PYTHONPATH` includes the repo root, or run pytest from the repo root with the venv activated:

```powershell
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
pytest -q tests/test_train_models.py
```

Recommendations
- For production-grade runs, set `--min-games` to a higher threshold (e.g. 50) to avoid overfitting on tiny per-player datasets.
- Increase `--trials` for more thorough hyperparameter search (costs more CPU/time). Consider running Optuna in parallel across players rather than parallelizing trials inside a single process.
- The script uses conservative fallbacks (randomized search) if Optuna isn't installed.

Troubleshooting
- If you see repeated Optuna trial values equal to `1.0`, that indicates trials returned the configured penalty (no valid folds or exceptions during fit). Check dataset splits and ensure fold creation returns non-empty validation sets.

Contact
- For questions about model formats or registry behavior, see `backend/services/model_registry.py` and `backend/services/simple_model_registry.py`.
