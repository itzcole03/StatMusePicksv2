# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2025-11-26

### Fixed
- Persist legacy flat model path into `model_metadata.path` for backward compatibility and tests.
- Align validation features (`X_val`) to `model._feature_list` in the orchestrator worker so calibrator
  fitting can predict without feature-mismatch errors and be persisted.

### Chores
- Formatted modified Python files (`backend/services/model_registry.py`, `backend/scripts/train_orchestrator.py`).


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

2025-11-17 — feat: Multi-season support, advanced metrics, and training pipeline integration

- Added season-aware retrieval to the low-level NBA client (`backend/services/nba_stats_client.py`): optional `season` parameter for recent games and team stats, and cache keys include the season.
- Implemented `get_advanced_player_stats` (league dashboard per-game metrics) with Redis + in-process TTLCache fallback.
- Extended the higher-level service (`backend/services/nba_service.py`) to accept `season` and added `get_player_context_for_training(player, stat, game_date, season)` to build season-scoped contexts for ML.
- Added `backend/services/training_data_service.py` to construct labeled training samples and datasets using the service-layer contexts and existing feature engineering utilities.
- Wired `backend/scripts/train_and_persist_real_model.py` to prefer real, season-scoped training data with a synthetic fallback when samples are unavailable.
- Added unit tests for the new training data pipeline and train script wiring: `backend/tests/test_training_data_service.py`, `backend/tests/test_train_script.py`.
- Fixed pytest collection collisions by removing duplicate top-level test modules (`tests/test_feature_engineering.py`, `tests/test_ml_prediction_service.py`) and cleaning compiled bytecode; full backend test suite and full repo pytest now pass (73 tests).

Notes:

- All changes include defensive handling when optional dependencies (e.g., `nba_api`) are missing; the system falls back to safe defaults for tests and CI.
- Caching remains Redis-first with a `cachetools.TTLCache` in-process fallback when Redis is not configured.
