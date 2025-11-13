# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2025-11-12

### Added
- Backend: Rolling statistics and opponent-adjusted features implemented and exposed via `/api/player_context`.
- Frontend: `nbaService` now consumes enhanced backend context; UI (`AnalysisSection`) renders rolling averages.
- Persisted a toy RandomForest model for dev/testing at `backend/models_store/LeBron_James.pkl`.
- Tests: Frontend mocks centralized for stable Vitest runs; backend compatibility unit test added for `nba_stats_client`.
- CI: Added gated workflow for live NBA integration tests `.github/workflows/live-nba-integration.yml` (run with `RUN_LIVE_NBA_TESTS=1` or manual dispatch).

### Changed
- Documentation: updated `ManusPlan/IMPLEMENTATION_ROADMAP.md` and `ManusPlan/technical_implementation_guide.md` to mark Task 1.5.1 complete and record CI gating decision.

### Notes
- Live NBA tests require `nba_api` to be installed in the Python environment and are intentionally gated to avoid CI flakiness.
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

2025-11-12 — feat: Add `/api/player_context` endpoint

- Implemented `/api/player_context` in the backend. The endpoint returns recent games, a derived `seasonAvg`, and enhanced numeric context when available (`rollingAverages`, `contextualFactors`, `opponentInfo`).
- Endpoint uses Redis caching (key: `player_context:{player_name}:{limit}`) when configured.
- Added unit tests for the endpoint and feature extraction helpers.
