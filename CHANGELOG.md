# Changelog

All notable changes to this project are documented in this file.

Unreleased
----------

2025-11-12 — feat: Add rolling statistics and toy model

- Added rolling statistics to the ML feature pipeline (`backend/services/feature_engineering.py`):
  - Moving averages: SMA (3/5/10), EMA (alpha tuned), WMA (3/5),
  - Rolling summary stats: std, min, max, median (3/5/10 windows),
  - `slope_10`: linear trend over last 10 games,
  - `momentum_vs_5_avg`: momentum metric relative to 5-game average.

- Wired the shared feature engineering into both training and prediction code paths to avoid feature drift.

- Added unit tests: `backend/tests/test_rolling_stats.py`.

- Persisted a toy RandomForest model locally during development at `backend/models_store/LeBron_James.pkl` (artifact not committed).

- Added GitHub Actions workflow `.github/workflows/backend-tests.yml` to run `pytest backend/tests` on pull requests.

Notes:

- Model artifacts (pickles) can be large and should be managed with Git LFS or as release artifacts; see README for guidance.
