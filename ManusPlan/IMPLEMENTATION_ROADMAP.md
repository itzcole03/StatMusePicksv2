# StatMusePicksV2 AI Service - Implementation Roadmap & Progress Tracker

**Version:** 1.0  
**Last Updated:** November 11, 2025
**Estimated Timeline:** 6-9 months  
**Status:** 🟡 In Progress

---

## 📊 Overall Progress Tracker

| Phase                          | Status         | Progress | Start Date | End Date | Notes                           |
| ------------------------------ | -------------- | -------- | ---------- | -------- | ------------------------------- |
| **Phase 1: Foundation**        | 🟡 In Progress | 72%      | -          | -        | Backend & Data Infrastructure   |
| **Phase 2: Core ML**           | 🔴 Not Started | 0%       | -          | -        | Per-Player Models & Calibration |
| **Phase 3: Advanced Features** | 🔴 Not Started | 0%       | -          | -        | Feature Engineering & Ensemble  |
| **Phase 4: Production**        | 🔴 Not Started | 0%       | -          | -        | MLOps & Automation              |

**Legend:**

- 🔴 Not Started
- 🟡 In Progress
- 🟢 Completed
- ⚠️ Blocked
- ⏸️ On Hold

---

# PHASE 1: FOUNDATIONAL DATA & BACKEND (1-2 Months)

**Objective:** Build core backend infrastructure and data pipeline  
**Status:** 🟡 In Progress  
**Progress:** 18/25 tasks completed

### Recent Progress (Nov 10-11, 2025)

- [x] Wired `aiService.v2` into the frontend analysis pipeline and UI.
- [x] Added E2E component test comparing LLM output with statistical evidence (`src/components/__tests__/AnalysisSection.e2e.test.tsx`).
- [x] Executed frontend E2E test locally (vitest) to verify agreement flow and UI behavior.
- [x] Added backend `ModelRegistry` and `ModelMetadata` model; `ModelRegistry.save_model` persists metadata.
- [x] Added Alembic migrations and initial `0001_initial` migration including `model_metadata` table.
- [x] Implemented ML prediction scaffold and model management endpoints (`/api/models`, `/api/models/load`, `/api/predict`).
- [x] Added integration test `tests/test_model_metadata.py` that runs migrations and training example to verify metadata insertion.
- [x] Added deterministic disagreement handling using `aiService.v2` to flag and null LLM recommendations when v2 strongly disagrees.
- [x] Added an E2E disagreement test `src/components/__tests__/AnalysisSection.disagreement.e2e.test.tsx` that verifies flagging behavior.

Additional updates (Nov 11, 2025):

- [x] Patched Alembic migrations to be tolerant of non-Timescale Postgres and fixed index migrations that referenced non-existent columns; added guards to skip Timescale-specific SQL when the extension isn't present.
- [x] Implemented Redis-backed cache with authoritative in-memory fallback and added sync-delete helper; unit & integration tests added and passing.
- [x] Created persisted toy model (`backend/models_store/LeBron_James.pkl`) for tests and updated tests to load it.
- [x] Ran Alembic migrations and full backend test suite locally against a disposable Postgres (all backend tests passing).
- [x] Ran TypeScript typecheck (`tsc --noEmit`) and ESLint across `src/` — no issues reported.

## 1.1 Backend Setup

### Task 1.1.1: Initialize Python Backend

- [ ] Create `backend/` directory structure
- [ ] Set up Python virtual environment (Python 3.9+)
- [x] Create `requirements.txt` with dependencies:
  - [ ] fastapi
  - [ ] uvicorn
  - [ ] pydantic
  - [ ] sqlalchemy
  - [ ] psycopg2-binary
  - [ ] redis
  - [ ] pandas
  - [ ] numpy
  - [ ] scikit-learn
  - [ ] xgboost
  - [ ] joblib
- [x] Create `backend/main.py` with FastAPI app
- [ ] Test basic FastAPI server runs on port 8000

**Acceptance Criteria:**

- ✅ FastAPI server starts without errors
- ✅ `/health` endpoint returns 200 OK
- ✅ All dependencies install successfully

Dev helper files added:

- [x] `backend/README.md` - run/install instructions
- [x] `backend/.env.example` - example env vars (Redis)
- [x] `backend/run_backend.ps1` - PowerShell helper to run server

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 1.1.2: Set Up Database Infrastructure

- [x] Install PostgreSQL 14+ locally or provision cloud instance (dev via `docker-compose.dev.yml`)
- [x] Create database: `statmuse_dev` (dev). Note: production DB `statmuse_predictions` is pending provisioning
- [ ] Install TimescaleDB extension for time-series data
 - [x] Install TimescaleDB extension for time-series data (staging enabled)
- [x] Create database schema:
  - [x] `players` table (id, name, team, position, etc.)
  - [x] `games` table (id, date, home_team, away_team, etc.)
  - [x] `player_stats` table (player_id, game_id, stat_type, value, date)
  - [x] `predictions` table (id, player_id, stat_type, predicted_value, actual_value, date)
  - [x] `models` table / `model_metadata` (id, player_name, version, path, notes, created_at)
- [x] Set up database migrations (Alembic) — migrations exist and were applied to dev Postgres
- [x] Create database connection pool in FastAPI (async engine + sessionmaker in `backend/db.py`)

**Status:** ✅ Completed (dev)

**Acceptance Criteria:**

- ✅ Database accessible from backend (dev stack)
- ✅ Schema created in dev Postgres (`players`, `projections`, `model_metadata`, `games`, `player_stats`, `predictions`)
- ✅ Can insert and query test data (smoke scripts / tests executed)

**Status:** 🟡 In Progress  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

**Progress notes (updated):**

- The dev DB stack has been provisioned via `docker-compose.dev.yml` and a Postgres container (`statmuse_postgres`) is running locally. The development DB used is `statmuse_dev` (accessible at `postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev`).
- Alembic migrations have been run against the dev Postgres instance and the migration that creates `games`, `player_stats`, and `predictions` was applied (see `backend/alembic/versions/0002_add_game_stats_predictions.py`).
- The original `0001_initial` migration and `model_metadata` table exist and were applied earlier. The `players` and `projections` tables from the initial migration are present.
- The backend now initializes an async SQLAlchemy engine and sessionmaker (see `backend/db.py` `_ensure_engine_and_session()`), and FastAPI startup hooks and a DB health endpoint were added/validated. This satisfies the "Create database connection pool in FastAPI" acceptance item for the dev environment.

**Completion notes (Nov 11, 2025):**

- Applied Alembic migrations to the development Postgres instance and added a targeted index migration for production hot queries (`backend/alembic/versions/0003_add_indexes.py`) which creates:
  - `ix_player_stats_player_id_game_date` on `player_stats(player_id, game_date)`
  - `ix_predictions_player_id_created_at` on `predictions(player_id, created_at)`

- Added a CI smoke test workflow that runs Alembic migrations against a disposable Postgres service and executes a lightweight DB health test (`.github/workflows/alembic_migration_smoke.yml`).

- Added developer helper `backend/scripts/persist_toy_model.py` and unit tests so the backend test-suite can validate model persistence and DB-related features locally.

- Verified local dev test run: `python -m pytest backend/tests` → all backend tests pass (6 passed, 10 warnings).

**Timescale staging notes (Nov 11, 2025):**

- A TimescaleDB staging container (`statmuse_timescale`) was started and the `timescaledb` extension was enabled for local benchmarking.
- Created an example hypertable `player_stats_ht` partitioned on `game_date` to exercise time-series queries and benchmark hypertable performance versus a regular table. This is for staging/testing only; production rollout requires managed Timescale or installing the extension into the production Postgres where allowed.

**Remaining / Not done yet for Task 1.1.2:**

- [x] Install TimescaleDB extension for time-series workloads (optional, production optimization) — Timescale staging container started and `timescaledb` extension enabled; example hypertable `player_stats_ht` created for local benchmarking.
- [x] Create production-grade index migrations for hot queries (added in `0003_add_indexes`).
- [x] Add schema migration smoke test in CI (`.github/workflows/alembic_migration_smoke.yml`) that runs Alembic migrations and a DB health test.
- [ ] Create production database and apply migrations in CI/deploy pipeline (`statmuse_predictions`) — requires provisioning and deployment privileges (see Next Steps).

**Immediate follow-ups (added):**
- [ ] Add Alembic index migration(s) for hot queries (e.g., `player_stats(player_id, game_date)`).
- [ ] Add a CI smoke test that runs Alembic migrations against a disposable test DB to validate `DATABASE_URL` handling.

**Recommended next actions (short-term, roadmap-aligned):**

 1. Provision production database (`statmuse_predictions`) and ensure secrets/`DATABASE_URL` are available to the deploy pipeline. Then run `alembic -c backend/alembic.ini upgrade head` in CI/CD deployment to apply migrations during release.
 2. After provisioning, run performance tuning and index analysis in a staging environment (use `EXPLAIN ANALYZE` on hot queries) and add any additional partial indexes or materialized views as Alembic migrations.
 3. Keep the existing CI smoke workflow (or extend `backend-ci.yml`) to run `pytest backend/tests` and the Alembic smoke test on PRs to prevent migration/DB regressions.

These updates maintain fidelity to the technical guide: migrations were applied, DB connectivity is wired into the FastAPI runtime, and toy model persistence/metadata insertion has been validated against the dev Postgres instance.

---

### Task 1.1.3: Set Up Redis Cache

- [x] Install Redis locally or provision cloud instance (dev via docker-compose)
- [x] Configure Redis connection in backend (`REDIS_URL` support)
- [x] Implement caching layer for:
  - [x] Player context data (TTL: 6 hours)
  - [x] Opponent stats (TTL: 24 hours)
  - [x] Model predictions (TTL: 1 hour)
- [x] Create cache invalidation logic and wire into model save/ingest flows
- [x] Add robust in-process fallback for local/dev so tests run without Redis
- [x] Test cache hit/miss scenarios (unit + integration tests added)

**Acceptance Criteria:**

- ✅ Redis accessible from backend (CI `redis-integration` job)
- ✅ Cache stores and retrieves data correctly (Redis and fallback)
- ✅ TTL expiration works as expected (unit tests)
- ✅ Cache invalidation verified end-to-end (integration test)

**Status:** ✅ Completed (dev)
**Assigned To:** Backend Team
**Completion Date:** Nov 11, 2025

**Notes:**
- Implemented an async Redis-backed cache with an authoritative in-process fallback in `backend/services/cache.py`.
- Added `redis_delete_prefix_sync` for synchronous callers and unit tests covering both no-loop and loop-running scenarios (`backend/tests/test_cache_sync_delete.py`).
- Wired invalidation into `ModelRegistry.save_model()` and ingestion/backfill to invalidate only affected player keys when possible.
- Added CI workflow `redis-integration` to run cache integration tests against a real Redis service.

---

## 1.2 Data Source Integration

### Task 1.2.1: Integrate NBA Stats API

- [x] Research NBA Stats API endpoints
- [x] Create `backend/services/nba_stats_client.py`
- [x] Implement functions (basic):
  - [x] `find_player_id_by_name(player_name)` → player ID
  - [x] `fetch_recent_games(player_id, limit)` → recent game logs
  - [x] `get_player_season_stats(player_id, season)` → season averages (implemented)
  - [ ] `get_team_stats(team_id)` → team offensive/defensive ratings (todo)
- [x] Add rate limiting (simple token-bucket, configurable)
- [x] Add retry logic with exponential backoff for upstream calls
- [x] Add unit tests that mock `nba_api`/Redis for client and `nba_service`

**Acceptance Criteria:**

- ✅ Basic player ID resolution and recent-games fetch implemented and tested (mocked)
- ✅ Rate limiting and retries in place for upstream requests
- ✅ Client handles API errors and falls back to best-effort logic

**Status:** 🟡 In Progress  
**Assigned To:** Backend Team  
**Completion Date:** in progress (Nov 11, 2025)

---

---

### Task 1.2.3: Build Data Ingestion Pipeline

- [x] Create `backend/services/data_ingestion_service.py`
- [x] Implement daily data sync:
  - [x] Fetch yesterday's game results
  - [x] Update player stats in database
  - [x] Update team stats
  - [x] Store raw data for auditing
- [x] Add data validation (initial + extended):
  - [x] Check for missing values
  - [x] Detect outliers (e.g., stat > 3 std deviations)
  - [x] Validate data types and ranges
 - [x] Create scheduled job (cron or Celery):
  - [x] Run daily at 6 AM EST (after games finish) — CLI + shell runner and systemd templates added
 - [~] Add logging and error notifications (in-progress)

**Acceptance Criteria:**

- ✅ Pipeline runs without manual intervention (scaffold and local runner implemented)
- ✅ Data validation: missing-values, type checks and outlier detection implemented and covered by unit tests
- ⚠️ Alerting: best-effort webhook posting implemented; integration with real webhook/SLACK/Sentry pending

**Status:** 🟡 In Progress  
**Assigned To:** Backend Team  
**Completion Date:** in progress

**Update Log (recent work):**

- Implemented `backend/services/data_ingestion_service.py` with:
  - `normalize_raw_game()` (canonical field mapping, date parsing, score normalization, team-name normalization)
  - `save_raw_games()` for raw-audit persistence
  - `update_player_stats()` and `update_team_stats()` that persist `Player`, `Game`, `PlayerStat` and compute/upsert `TeamStat` aggregates
- Added `backend/models/team_stat.py` and Alembic migration `backend/alembic/versions/0007_add_team_stats.py`.
- Added file-based team mapping `backend/data/team_abbrevs.json` and wired loader into normalization.
- Implemented validation helpers and tests: `detect_missing_values`, `validate_record_types`, `detect_outliers`, `validate_batch` and unit tests under `backend/tests`.
- Wired validation into `run_daily_sync()` so records missing critical fields are filtered and a validation summary is returned. Validation findings are sent as a best-effort POST to `INGEST_ALERT_WEBHOOK` (or logged when unset).
- Added `scripts/run_daily_sync_example.ps1` — PowerShell runner for manual/testing runs and scheduling.

**Next steps:**

- Verify scheduled runner in target environment (create systemd service/timer or Task Scheduler entry). Use `scripts/run_daily_sync_example.ps1` (Windows) or `scripts/run_daily_sync.sh` (Linux) to schedule the job.
- Harden alerting (add secret header, retries, and test webhook integration) and add an integration test that simulates a webhook. (HMAC + retries already implemented; consider rotating secrets and storing in GitHub Actions/Secrets.)
 - Add monitoring (Grafana/Prometheus) for job success/failure metrics and wire alerts to Slack/Sentry.

Recent tooling added:

- Added `scripts/run_daily_sync_example.ps1` — a small PowerShell example that activates the virtualenv, sets `INGEST_AUDIT_DIR`, optionally configures `INGEST_ALERT_WEBHOOK`, runs `run_daily_sync()` and prints the result. Use this script as a manual runner or as the command executed by a scheduled task.

Scheduling guidance (example):

- On Windows: add a Task Scheduler job that runs PowerShell and calls `scripts\run_daily_sync_example.ps1` daily at 06:00.
- On Linux: a cron entry that activates your venv and calls a similarly-constructed shell script that runs:
  - `python -c "from backend.services.data_ingestion_service import run_daily_sync; print(run_daily_sync())"`



---

## 1.3 Feature Engineering Pipeline

### Task 1.3.1: Implement Basic Feature Engineering

- [x] Create `backend/services/feature_engineering.py`
- [x] Implement `FeatureEngineering` class
- [x] Add basic features:
  - [x] Recent performance (last 3, 5, 10 games averages)
  - [x] Season average
  - [x] Home/away indicator
  - [x] Days of rest
  - [x] Back-to-back game indicator
- [x] Create feature extraction function:
  - [x] Input: player_id, game_date
  - [x] Output: feature DataFrame
- [x] Test with 10 different players

**Acceptance Criteria:**

- ✅ Features calculated correctly
- ✅ Handles missing data gracefully
- ✅ Returns consistent DataFrame schema

**Status:** ✅ Completed (dev)  
**Assigned To:** Backend Team  
**Completion Date:** Nov 12, 2025

**Progress update (Nov 12, 2025):**

- [x] Created `backend/services/feature_engineering.py` and added unit tests under `backend/tests/test_feature_engineering.py`.
- [x] Implemented `FeatureEngineering` compatibility wrapper and top-level `engineer_features` that returns a `pandas.DataFrame` ready for model input.
- [x] Implemented basic features: recent performance (last 3/5/10), season average, home/away indicator, days-of-rest, rolling averages, EMA, and simple imputations. Unit tests validate recent stats and rolling calculations.
 - [x] Back-to-back game indicator: implemented and exposed as `contextualFactors.daysRest` and `contextualFactors.isBackToBack` in the `player_context` API response. Frontend types and `nbaService` normalization updated to consume these fields.
- [x] Feature extraction function present and covered by unit tests; additional coverage (10+ players) is recommended.

**Status:** ✅ Completed (dev) — partial enhancement pending (back-to-back indicator)
**Assigned To:** Backend Team
**Completion Date:** Nov 12, 2025

---

### Task 1.3.2: Add Rolling Statistics

- [x] Implement rolling averages:
  - [x] Simple Moving Average (SMA) for 3, 5, 10 games
  - [x] Exponential Moving Average (EMA) with alpha=0.3
  - [x] Weighted Moving Average (recent games weighted higher)
- [x] Implement rolling statistics:
  - [x] Rolling standard deviation
  - [x] Rolling min/max
  - [x] Rolling median
- [x] Add trend detection:
  - [x] Linear regression slope over last 10 games
  - [x] Momentum indicator (current vs 5-game avg)
- [x] Test on historical data

**Acceptance Criteria:**

- ✅ Rolling calculations match manual verification
- ✅ Handles edge cases (< 3 games available)
- ✅ Performance acceptable (< 100ms per player)

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

**Progress update (Nov 12, 2025):**

- ✅ Implemented SMA (3/5/10), EMA (alpha=0.3), and WMA (3/5).  
- ✅ Added rolling std/min/max/median for 3/5/10 windows.  
- ✅ Added linear slope over last 10 games and `momentum_vs_5_avg` indicator.  
- ✅ Unit tests added under `backend/tests` and validated locally.
- ✅ FeatureEngineering and training scripts updated to include new features.

**Status:** ✅ Completed (dev)
**Completion Date:** Nov 12, 2025

---

### Task 1.3.3: Add Opponent-Adjusted Features

- [ ] Implement opponent strength metrics:
  - [ ] Opponent defensive rating
  - [ ] Opponent pace of play
  - [ ] Opponent rank (1-30)
- [ ] Calculate opponent-adjusted stats:
  - [ ] Player avg vs top-10 defenses
  - [ ] Player avg vs bottom-10 defenses
  - [ ] Player avg vs similar opponents
- [ ] Add historical matchup data:
  - [ ] Games vs current opponent
  - [ ] Avg performance vs current opponent
  - [ ] Last game vs current opponent
- [ ] Test with rivalry matchups (LAL vs BOS, etc.)

**Acceptance Criteria:**

- ✅ Opponent adjustments calculated correctly
- ✅ Historical matchup data retrieved
- ✅ Handles new matchups (no history)

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 1.4 API Endpoints

### Task 1.4.1: Create Player Context Endpoint

- [ ] Implement `/api/player_context` endpoint
- [ ] Accept parameters:
  - [ ] `player_name` (string)
  - [ ] `stat_type` (string: points, rebounds, assists, etc.)
  - [ ] `game_date` (date)
- [ ] Return enhanced player context:
  - [ ] Recent games
  - [ ] Season average
  - [ ] Advanced metrics
  - [ ] Rolling averages
  - [ ] Opponent info
- [ ] Add response caching (Redis, 6-hour TTL)
- [ ] Add API documentation (Swagger)

**Acceptance Criteria:**

- ✅ Endpoint returns 200 OK for valid requests
- ✅ Returns 404 for unknown players
- ✅ Response time < 500ms (with cache)
- ✅ Swagger docs accessible at `/docs`

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 1.4.2: Create Batch Context Endpoint

- [x] Implement `/api/batch_player_context` endpoint
 - [x] Accept list of player requests
 - [x] Process in parallel (asyncio)
 - [x] Return list of player contexts
 - [x] Add rate limiting (max 50 players per request)
 - [x] Optimize database queries (batch fetch)

**Acceptance Criteria:**

- ✅ Handles 50 players in < 3 seconds
- ✅ Returns partial results if some players fail
- ✅ Rate limiting works correctly

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 1.5 Frontend Integration

### Task 1.5.1: Update nbaService.ts to Use New Backend

- [ ] Update `fetchPlayerContextFromNBA()` function
- [ ] Point to new backend endpoint: `http://localhost:8000/api/player_context`
- [ ] Update response parsing to handle new data structure
- [ ] Add error handling for backend failures
- [ ] Test with existing frontend components

**Acceptance Criteria:**

- ✅ Frontend successfully fetches data from new backend
- ✅ Existing UI components work without changes
- ✅ Error messages displayed to user

**Status:** ✅ Completed (dev)
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 1.5.2: Update Frontend Types

- [ ] Update `types.ts` with new data structures:
  - [ ] `EnhancedPlayerContext` interface
  - [ ] `AdvancedMetrics` interface
  - [ ] `RollingAverages` interface
  - [ ] `ContextualFactors` interface
- [ ] Update components to display new data:
  - [ ] Show rolling averages in stats section
  - [ ] Display opponent-adjusted stats
  - [ ] Show trend indicators (↑↓)
- [ ] Test UI with new data

**Acceptance Criteria:**

- ✅ TypeScript compiles without errors
- ✅ UI displays new features correctly
- ✅ No console errors

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## Phase 1 Completion Checklist

**Before moving to Phase 2, verify:**

- [ ] ✅ Python backend running and accessible
- [ ] ✅ Database schema created and populated with test data
- [ ] ✅ Redis cache working
- [ ] ✅ NBA Stats API integration functional
- [ ] ✅ Basic feature engineering pipeline working
- [ ] ✅ API endpoints returning correct data
- [ ] ✅ Frontend successfully using new backend
- [ ] ✅ All Phase 1 unit tests passing
- [ ] ✅ Documentation updated

**Phase 1 Sign-Off:**

- [ ] Technical Lead Approval: ******\_****** Date: ******\_******
- [ ] Code Review Completed: ******\_****** Date: ******\_******
- [ ] Ready for Phase 2: ☐ Yes ☐ No

---

# PHASE 2: CORE ML MODELS & CALIBRATION (2-3 Months)

**Objective:** Implement per-player ML models with proper calibration  
**Status:** 🟡 In Progress  
**Progress:** 3/20 tasks completed

## 2.1 Model Training Infrastructure

### Task 2.1.1: Set Up Training Data Pipeline

- [ ] Create `backend/services/training_data_service.py`
- [ ] Implement function to generate training dataset:
  - [ ] Query historical player stats from database
  - [ ] Join with game results (actual outcomes)
  - [ ] Apply feature engineering
  - [ ] Create target variable (stat value)
- [ ] Implement train/validation/test split:
  - [ ] Use time-based split (not random)
  - [ ] Train: 70% (oldest data)
  - [ ] Validation: 15%
  - [ ] Test: 15% (most recent data)
- [ ] Save datasets to disk (parquet format)
- [ ] Create data versioning system

**Acceptance Criteria:**

- ✅ Training data generated for 10 test players
- ✅ Train/val/test splits have no data leakage
- ✅ Dataset includes at least 50 games per player

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.1.2: Implement Model Registry

- [ ] Create `backend/services/model_registry.py`
- [ ] Implement `PlayerModelRegistry` class:
  - [ ] Store models in dictionary: `{player_name: model}`
  - [ ] Save models to disk: `models/{player_name}_v{version}.pkl`
  - [ ] Load models from disk on startup
  - [ ] Track model versions and metadata
- [ ] Add model metadata:
  - [ ] Training date
  - [ ] Model type (RandomForest, XGBoost, etc.)
  - [ ] Performance metrics (MAE, RMSE, Brier score)
  - [ ] Feature importance
- [ ] Implement model versioning

**Acceptance Criteria:**

- ✅ Models persist across server restarts
- ✅ Can load specific model versions
- ✅ Metadata tracked correctly

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.1.3: Create Training Pipeline

- [ ] Create `backend/training/train_models.py` script
- [ ] Implement training loop:
  - [ ] For each player with sufficient data (50+ games):
    - [ ] Load training data
    - [ ] Train Random Forest model
    - [ ] Train XGBoost model
    - [ ] Train Elastic Net model
    - [ ] Evaluate on validation set
    - [ ] Save best model to registry
- [ ] Add hyperparameter tuning (Optuna):
  - [ ] Optimize for Brier score (not accuracy)
  - [ ] Run 50 trials per model
- [ ] Add progress tracking and logging
- [ ] Create training report (CSV with metrics)

**Acceptance Criteria:**

- ✅ Training completes for 10 test players
- ✅ Models saved to registry
- ✅ Training report generated

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 2.2 Model Implementation

### Task 2.2.1: Implement Random Forest Model

- [ ] Create `backend/models/random_forest_model.py`
- [ ] Configure hyperparameters:
  - [ ] `n_estimators`: 100-200
  - [ ] `max_depth`: 5-15
  - [ ] `min_samples_split`: 5-20
  - [ ] `min_samples_leaf`: 2-10
- [ ] Implement training function
- [ ] Implement prediction function
- [ ] Add feature importance extraction
- [ ] Test on sample data

**Acceptance Criteria:**

- ✅ Model trains successfully
- ✅ Predictions are reasonable (within expected range)
- ✅ Feature importance calculated

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.2.2: Implement XGBoost Model

- [ ] Create `backend/models/xgboost_model.py`
- [ ] Configure hyperparameters:
  - [ ] `n_estimators`: 100-200
  - [ ] `max_depth`: 3-10
  - [ ] `learning_rate`: 0.01-0.3
  - [ ] `subsample`: 0.7-1.0
  - [ ] `colsample_bytree`: 0.7-1.0
- [ ] Implement training function with early stopping
- [ ] Implement prediction function
- [ ] Add SHAP value calculation (optional)
- [ ] Test on sample data

**Acceptance Criteria:**

- ✅ Model trains successfully
- ✅ Early stopping prevents overfitting
- ✅ Predictions comparable to Random Forest

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.2.3: Implement Elastic Net Model

- [ ] Create `backend/models/elastic_net_model.py`
- [ ] Configure hyperparameters:
  - [ ] `alpha`: 0.01-1.0
  - [ ] `l1_ratio`: 0.1-0.9
- [ ] Implement training function
- [ ] Implement prediction function
- [ ] Add coefficient extraction
- [ ] Test on sample data

**Acceptance Criteria:**

- ✅ Model trains successfully
- ✅ Serves as good baseline
- ✅ Coefficients interpretable

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.2.4: Implement Ensemble Model

- [ ] Create `backend/models/ensemble_model.py`
- [ ] Implement `VotingRegressor`:
  - [ ] Combine Random Forest, XGBoost, Elastic Net
  - [ ] Weights: [0.4, 0.4, 0.2]
- [ ] Implement stacking ensemble (optional):
  - [ ] Use meta-learner (Ridge regression)
- [ ] Test ensemble vs individual models
- [ ] Compare performance metrics

**Acceptance Criteria:**

- ✅ Ensemble model trains successfully
- ✅ Performance >= best individual model
- ✅ Predictions are stable

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 2.3 Model Calibration

### Task 2.3.1: Implement Isotonic Regression Calibration

- [ ] Create `backend/services/calibration_service.py`
- [ ] Implement `CalibratorRegistry` class
- [ ] For each trained model:
  - [ ] Get predictions on validation set
  - [ ] Fit isotonic regression: `predicted → actual`
  - [ ] Save calibrator to registry
- [ ] Implement calibrated prediction function:
  - [ ] Get raw model prediction
  - [ ] Apply calibrator
  - [ ] Return calibrated prediction
- [ ] Test calibration improves Brier score

**Acceptance Criteria:**

- ✅ Calibrators trained for all models
- ✅ Calibrated predictions more accurate
- ✅ Brier score improves by 10%+

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.3.2: Implement Calibration Metrics

- [ ] Create `backend/evaluation/calibration_metrics.py`
- [ ] Implement Brier Score calculation:
  - [ ] Formula: `(1/N) * Σ(predicted_prob - actual)²`
- [ ] Implement Expected Calibration Error (ECE):
  - [ ] Bin predictions into 10 buckets
  - [ ] Calculate accuracy per bucket
  - [ ] Compute weighted average error
- [ ] Implement reliability diagram plotting
- [ ] Test on validation data

**Acceptance Criteria:**

- ✅ Metrics calculated correctly
- ✅ Reliability diagrams generated
- ✅ Can compare calibrated vs uncalibrated

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 2.4 Prediction Service

-### Task 2.4.1: Implement ML Prediction Service

- [x] Create `backend/services/ml_prediction_service.py`
- [ ] Implement `MLPredictionService` class
- [ ] Implement `predict()` function:
  - [ ] Input: player_name, stat_type, line, features
  - [ ] Get player model from registry
  - [ ] Make raw prediction
  - [ ] Apply calibration
  - [ ] Calculate over/under probability
  - [ ] Calculate expected value
  - [ ] Return prediction result
- [ ] Add fallback logic for players without models
- [ ] Test with 10 different players

**Acceptance Criteria:**

- ✅ Predictions generated successfully
- ✅ Probabilities sum to 1.0
- ✅ Fallback works for new players

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

-### Task 2.4.2: Create Prediction API Endpoint

- [x] Implement `/api/predict` endpoint
- [x] Implement `/api/batch_predict` endpoint
- [ ] Accept request body:
  ```json
  {
    "player": "LeBron James",
    "stat": "points",
    "line": 25.5,
    "player_data": {...},
    "opponent_data": {...}
  }
  ```
- [ ] Return prediction response:
  ```json
  {
    "player": "LeBron James",
    "predicted_value": 27.3,
    "over_probability": 0.68,
    "recommendation": "OVER",
    "confidence": 68,
    "expected_value": 0.12
  }
  ```
- [ ] Add request validation
- [ ] Add response caching (1-hour TTL)
- [ ] Test with Postman/curl

**Acceptance Criteria:**

- ✅ Endpoint returns 200 OK
- ✅ Response format correct
- ✅ Caching works

**Status:** ✅ Completed (dev)  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.4.3: Create Batch Prediction Endpoint

- [ ] Implement `/api/batch_predict` endpoint
- [ ] Accept list of prediction requests
- [ ] Process in parallel (asyncio)
- [ ] Return list of predictions
- [ ] Add timeout handling (30 seconds max)
- [ ] Test with 20 simultaneous requests

**Acceptance Criteria:**

- ✅ Handles 20 predictions in < 5 seconds
- ✅ Returns partial results if some fail
- ✅ No memory leaks

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 2.5 Backtesting Engine

### Task 2.5.1: Implement Backtesting Framework

- [ ] Create `backend/evaluation/backtesting.py`
- [ ] Implement `BacktestEngine` class
- [ ] Load historical predictions and actual results
- [ ] Simulate betting strategy:
  - [ ] Only bet when EV > 0
  - [ ] Only bet when confidence > 60%
  - [ ] Use Kelly Criterion for stake sizing (2% of bankroll)
- [ ] Calculate metrics:
  - [ ] Final bankroll
  - [ ] ROI (%)
  - [ ] Win rate (%)
  - [ ] Total bets
  - [ ] Sharpe ratio
- [ ] Generate backtest report

**Acceptance Criteria:**

- ✅ Backtesting runs on historical data
- ✅ ROI calculated correctly
- ✅ Report generated (CSV + charts)

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 2.5.2: Run Initial Backtest

- [ ] Backtest on 2023-2024 season data
- [ ] Test multiple strategies:
  - [ ] Strategy 1: Bet all predictions with EV > 0
  - [ ] Strategy 2: Bet only high-confidence (>70%)
  - [ ] Strategy 3: Bet only underdogs (line < season avg)
- [ ] Compare strategies
- [ ] Identify best-performing strategy
- [ ] Document results

**Acceptance Criteria:**

- ✅ At least one strategy shows positive ROI
- ✅ Results documented in report
- ✅ Insights identified for improvement

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## Phase 2 Completion Checklist

**Before moving to Phase 3, verify:**

- [ ] ✅ Per-player models trained for 50+ players
- [ ] ✅ Model calibration implemented and tested
- [ ] ✅ Brier score < 0.20 on validation set
- [ ] ✅ Prediction API endpoints functional
- [ ] ✅ Backtesting shows positive ROI (>5%)
- [ ] ✅ All Phase 2 unit tests passing
- [ ] ✅ Documentation updated

**Phase 2 Sign-Off:**

- [ ] Technical Lead Approval: ******\_****** Date: ******\_******
- [ ] Code Review Completed: ******\_****** Date: ******\_******
- [ ] Ready for Phase 3: ☐ Yes ☐ No

---

# PHASE 3: ADVANCED FEATURES & OPTIMIZATION (2-3 Months)

**Objective:** Add advanced features and optimize model performance  
**Status:** 🔴 Not Started  
**Progress:** 0/15 tasks completed

## 3.1 Advanced Feature Engineering

### Task 3.1.1: Add Advanced NBA Metrics

- [ ] Integrate advanced stats from commercial API
- [ ] Add features:
  - [ ] Player Efficiency Rating (PER)
  - [ ] True Shooting % (TS%)
  - [ ] Usage Rate (USG%)
  - [ ] Player Impact Estimate (PIE)
  - [ ] Offensive Rating (ORtg)
  - [ ] Defensive Rating (DRtg)
  - [ ] Win Shares (WS)
  - [ ] Box Plus/Minus (BPM)
- [ ] Update feature engineering pipeline
- [ ] Retrain models with new features
- [ ] Compare performance vs baseline

**Acceptance Criteria:**

- ✅ Advanced metrics fetched successfully
- ✅ Features integrated into pipeline
- ✅ Model performance improves by 5%+

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 3.1.2: Add Player Tracking Features (Optional)

- [ ] Integrate player tracking data (if available)
- [ ] Add features:
  - [ ] Average speed
  - [ ] Distance covered per game
  - [ ] Touches per game
  - [ ] Time of possession
  - [ ] Shot quality (expected FG%)
- [ ] Test impact on model accuracy
- [ ] Document findings

**Acceptance Criteria:**

- ✅ Tracking data integrated (if available)
- ✅ Features improve model performance
- ✅ Cost-benefit analysis documented

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 3.1.3: Add Contextual Features

- [ ] Add game context features:
  - [ ] Playoff vs regular season
  - [ ] Rivalry games (LAL vs BOS, etc.)
  - [ ] Nationally televised games
  - [ ] Time zone travel distance
  - [ ] Altitude (Denver effect)
  - [ ] Game importance (playoff implications)
- [ ] Add player context features:
  - [ ] Contract year indicator
  - [ ] All-Star selection
  - [ ] Recent awards/recognition
  - [ ] Trade rumors (sentiment analysis)
- [ ] Test feature importance
- [ ] Keep only significant features

**Acceptance Criteria:**

- ✅ Contextual features added
- ✅ Feature importance analyzed
- ✅ Low-importance features removed

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 3.2 LLM Integration for Qualitative Features

### Task 3.2.1: Implement LLM Feature Extraction

- [ ] Create `backend/services/llm_feature_service.py`
- [ ] Use LLM to extract qualitative features:
  - [ ] Injury status sentiment (from news)
  - [ ] Team morale (from news/social media)
  - [ ] Motivation level (contract year, rivalry, etc.)
  - [ ] Coaching changes impact
- [ ] Convert text to numeric features (sentiment scores)
- [ ] Cache LLM results (expensive)
- [ ] Test on 10 players

**Acceptance Criteria:**

- ✅ LLM generates qualitative features
- ✅ Features are numeric and usable
- ✅ Caching reduces API costs

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 3.2.2: Integrate LLM Features into Models

- [ ] Add LLM features to feature engineering pipeline
- [ ] Retrain models with LLM features
- [ ] Compare performance:
  - [ ] With LLM features
  - [ ] Without LLM features
- [ ] Analyze feature importance
- [ ] Document ROI of LLM features

**Acceptance Criteria:**

- ✅ LLM features integrated
- ✅ Performance impact measured
- ✅ Cost-benefit analysis completed

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 3.3 Model Optimization

### Task 3.3.1: Hyperparameter Optimization

- [ ] Use Optuna for hyperparameter tuning
- [ ] Optimize each model type:
  - [ ] Random Forest (n_estimators, max_depth, etc.)
  - [ ] XGBoost (learning_rate, max_depth, etc.)
  - [ ] Elastic Net (alpha, l1_ratio)
- [ ] Run 100 trials per model
- [ ] Save best hyperparameters
- [ ] Retrain all models with optimal hyperparameters

**Acceptance Criteria:**

- ✅ Hyperparameter tuning completed
- ✅ Best parameters documented
- ✅ Model performance improves by 3%+

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 3.3.2: Feature Selection

- [ ] Implement feature selection methods:
  - [ ] Recursive Feature Elimination (RFE)
  - [ ] Feature importance from Random Forest
  - [ ] LASSO regularization (L1)
  - [ ] Correlation analysis
- [ ] Remove low-importance features
- [ ] Retrain models with selected features
- [ ] Compare performance and training time

**Acceptance Criteria:**

- ✅ Feature selection completed
- ✅ Number of features reduced by 20%+
- ✅ Model performance maintained or improved

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 3.3.3: Ensemble Optimization

- [ ] Experiment with ensemble weights:
  - [ ] Test different weight combinations
  - [ ] Use validation set to optimize
- [ ] Try stacking ensemble:
  - [ ] Use meta-learner (Ridge, Lasso)
  - [ ] Compare to voting ensemble
- [ ] Implement blending:
  - [ ] Combine predictions from multiple models
  - [ ] Optimize blend weights
- [ ] Select best ensemble strategy

**Acceptance Criteria:**

- ✅ Optimal ensemble weights found
- ✅ Best ensemble strategy selected
- ✅ Performance improves by 2%+

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 3.4 Model Specialization

### Task 3.4.1: Stat-Type Specific Models

- [ ] Train separate models for each stat type:
  - [ ] Points model
  - [ ] Rebounds model
  - [ ] Assists model
  - [ ] 3-pointers model
  - [ ] Steals/blocks model
- [ ] Use stat-specific features:
  - [ ] Points: shooting %, usage rate
  - [ ] Rebounds: height, opponent pace
  - [ ] Assists: team pace, ball handling
- [ ] Compare to generic models
- [ ] Document performance gains

**Acceptance Criteria:**

- ✅ Stat-specific models trained
- ✅ Performance compared to generic
- ✅ Best approach selected

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 3.4.2: Position-Specific Models (Optional)

- [ ] Train separate models for each position:
  - [ ] Point Guard (PG)
  - [ ] Shooting Guard (SG)
  - [ ] Small Forward (SF)
  - [ ] Power Forward (PF)
  - [ ] Center (C)
- [ ] Use position-specific features
- [ ] Compare to generic models
- [ ] Document findings

**Acceptance Criteria:**

- ✅ Position-specific models trained
- ✅ Performance compared
- ✅ Decision documented

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 3.5 Performance Optimization

### Task 3.5.1: Optimize Prediction Latency

- [ ] Profile prediction pipeline
- [ ] Identify bottlenecks:
  - [ ] Feature engineering
  - [ ] Model inference
  - [ ] Database queries
- [ ] Optimize slow components:
  - [ ] Cache frequently used data
  - [ ] Batch database queries
  - [ ] Use faster model formats (ONNX)
- [ ] Target: < 200ms per prediction

**Acceptance Criteria:**

- ✅ Prediction latency < 200ms (95th percentile)
- ✅ Bottlenecks identified and fixed
- ✅ Performance benchmarks documented

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 3.5.2: Optimize Training Pipeline

- [ ] Profile training pipeline
- [ ] Parallelize training:
  - [ ] Train multiple player models simultaneously
  - [ ] Use multiprocessing or Ray
- [ ] Optimize hyperparameter tuning:
  - [ ] Use parallel trials
  - [ ] Early stopping for bad trials
- [ ] Target: Train 200 models in < 4 hours

**Acceptance Criteria:**

- ✅ Training time reduced by 50%+
- ✅ Can train all models overnight
- ✅ Resource usage optimized

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## Phase 3 Completion Checklist

**Before moving to Phase 4, verify:**

- [ ] ✅ Advanced features integrated and tested
- [ ] ✅ Model performance improved by 10%+ vs Phase 2
- [ ] ✅ Brier score < 0.18 on validation set
- [ ] ✅ Backtesting ROI > 15%
- [ ] ✅ Prediction latency < 200ms
- [ ] ✅ All Phase 3 unit tests passing
- [ ] ✅ Documentation updated

**Phase 3 Sign-Off:**

- [ ] Technical Lead Approval: ******\_****** Date: ******\_******
- [ ] Code Review Completed: ******\_****** Date: ******\_******
- [ ] Ready for Phase 4: ☐ Yes ☐ No

---

# PHASE 4: PRODUCTION & MLOPS (Ongoing)

**Objective:** Deploy to production and automate ML lifecycle  
**Status:** 🔴 Not Started  
**Progress:** 0/18 tasks completed

## 4.1 MLOps Infrastructure

### Task 4.1.1: Set Up MLflow

- [ ] Install MLflow
- [ ] Configure MLflow tracking server
- [ ] Integrate with training pipeline:
  - [ ] Log hyperparameters
  - [ ] Log metrics (MAE, RMSE, Brier score)
  - [ ] Log model artifacts
  - [ ] Log feature importance
- [ ] Create MLflow UI dashboard
- [ ] Test with sample training run

**Acceptance Criteria:**

- ✅ MLflow tracking server running
- ✅ Training runs logged successfully
- ✅ UI accessible and functional

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.1.2: Implement Model Versioning

- [ ] Use MLflow Model Registry
- [ ] Register models with versions:
  - [ ] Version format: `v{YYYY-MM-DD}-{player_name}`
- [ ] Tag models:
  - [ ] `production` - currently deployed
  - [ ] `staging` - ready for testing
  - [ ] `archived` - old versions
- [ ] Implement model promotion workflow:
  - [ ] Staging → Production (manual approval)
- [ ] Test model rollback

**Acceptance Criteria:**

- ✅ Models versioned correctly
- ✅ Can promote/demote models
- ✅ Rollback works

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.1.3: Set Up Automated Training Pipeline

- [ ] Create training orchestration (Airflow or Prefect)
- [ ] Define training DAG:
  - [ ] Step 1: Fetch latest data
  - [ ] Step 2: Generate training dataset
  - [ ] Step 3: Train models
  - [ ] Step 4: Evaluate models
  - [ ] Step 5: Register models
  - [ ] Step 6: Generate report
- [ ] Schedule training:
  - [ ] Daily: High-volume players (30+ games)
  - [ ] Weekly: All players
- [ ] Add failure notifications (email/Slack)

**Acceptance Criteria:**

- ✅ Training pipeline runs automatically
- ✅ Schedule works correctly
- ✅ Failures trigger alerts

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 4.2 Monitoring & Alerting

### Task 4.2.1: Implement Model Performance Monitoring

- [ ] Create `backend/monitoring/model_monitor.py`
- [ ] Track daily metrics:
  - [ ] Prediction accuracy
  - [ ] Calibration error
  - [ ] ROI (simulated bets)
  - [ ] Prediction volume
- [ ] Store metrics in database
- [ ] Create monitoring dashboard (Grafana or custom)
- [ ] Set up alerts:
  - [ ] Accuracy < 60%
  - [ ] Calibration error > 0.20
  - [ ] ROI negative for 7+ days

**Acceptance Criteria:**

- ✅ Metrics tracked daily
- ✅ Dashboard shows real-time metrics
- ✅ Alerts trigger correctly

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.2.2: Implement Data Quality Monitoring

- [ ] Monitor data pipeline:
  - [ ] Missing data rate
  - [ ] Outlier detection
  - [ ] Data freshness (last update time)
  - [ ] API failure rate
- [ ] Set up alerts:
  - [ ] Missing data > 10%
  - [ ] Data not updated in 24 hours
  - [ ] API failures > 5%
- [ ] Create data quality dashboard

**Acceptance Criteria:**

- ✅ Data quality metrics tracked
- ✅ Alerts trigger for data issues
- ✅ Dashboard accessible

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.2.3: Implement Drift Detection

- [ ] Monitor feature drift:
  - [ ] Compare feature distributions over time
  - [ ] Detect significant changes (KS test)
- [ ] Monitor prediction drift:
  - [ ] Compare prediction distributions
  - [ ] Detect concept drift
- [ ] Trigger retraining when drift detected
- [ ] Log drift events

**Acceptance Criteria:**

- ✅ Drift detection runs daily
- ✅ Significant drift triggers alerts
- ✅ Retraining triggered automatically

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 4.3 A/B Testing

### Task 4.3.1: Implement A/B Testing Framework

- [ ] Create `backend/services/ab_testing_service.py`
- [ ] Implement traffic splitting:
  - [ ] 50% to model version A
  - [ ] 50% to model version B
- [ ] Track results per version:
  - [ ] Accuracy
  - [ ] Calibration
  - [ ] ROI
- [ ] Implement statistical significance testing
- [ ] Create A/B test report

**Acceptance Criteria:**

- ✅ Traffic splits correctly
- ✅ Results tracked per version
- ✅ Statistical tests implemented

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.3.2: Run A/B Tests

- [ ] Test 1: New features vs baseline
- [ ] Test 2: Ensemble vs single model
- [ ] Test 3: Calibrated vs uncalibrated
- [ ] Run each test for 2 weeks
- [ ] Analyze results
- [ ] Promote winning version

**Acceptance Criteria:**

- ✅ Tests run for full duration
- ✅ Results statistically significant
- ✅ Best version deployed

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 4.4 Production Deployment

### Task 4.4.1: Set Up Production Environment

- [ ] Provision production servers:
  - [ ] API server (2+ instances for redundancy)
  - [ ] Database (with replication)
  - [ ] Redis cache
  - [ ] MLflow server
- [ ] Configure load balancer
- [ ] Set up SSL certificates (HTTPS)
- [ ] Configure firewall rules
- [ ] Set up monitoring (Datadog, New Relic, or Prometheus)

**Acceptance Criteria:**

- ✅ Production environment accessible
- ✅ Load balancer distributes traffic
- ✅ HTTPS working
- ✅ Monitoring configured

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.4.2: Implement CI/CD Pipeline

- [ ] Set up GitHub Actions or GitLab CI
- [ ] Create CI pipeline:
  - [ ] Run unit tests
  - [ ] Run integration tests
  - [ ] Lint code (flake8, black)
  - [ ] Type check (mypy)
  - [ ] Build Docker image
- [ ] Create CD pipeline:
  - [ ] Deploy to staging on merge to `develop`
  - [ ] Deploy to production on merge to `main` (manual approval)
- [ ] Test full pipeline

**Acceptance Criteria:**

- ✅ CI runs on every commit
- ✅ CD deploys to staging automatically
- ✅ Production deployment requires approval

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.4.3: Implement Blue-Green Deployment

- [ ] Set up blue-green deployment:
  - [ ] Blue environment (current production)
  - [ ] Green environment (new version)
- [ ] Deploy new version to green
- [ ] Run smoke tests on green
- [ ] Switch traffic to green
- [ ] Keep blue as backup
- [ ] Test rollback procedure

**Acceptance Criteria:**

- ✅ Can deploy without downtime
- ✅ Rollback works in < 5 minutes
- ✅ Zero failed requests during deployment

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 4.5 Documentation & Knowledge Transfer

### Task 4.5.1: Create System Documentation

- [ ] Document architecture:
  - [ ] System architecture diagram
  - [ ] Data flow diagram
  - [ ] Component interaction diagram
- [ ] Document APIs:
  - [ ] OpenAPI/Swagger spec
  - [ ] Request/response examples
  - [ ] Error codes and handling
- [ ] Document data models:
  - [ ] Database schema
  - [ ] Feature definitions
  - [ ] Model inputs/outputs

**Acceptance Criteria:**

- ✅ Documentation complete and accurate
- ✅ Diagrams clear and up-to-date
- ✅ API docs auto-generated

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.5.2: Create Operational Runbooks

- [ ] Create runbooks for:
  - [ ] Model retraining procedure
  - [ ] Incident response (API down, predictions failing)
  - [ ] Database backup/restore
  - [ ] Scaling procedures (add more servers)
  - [ ] Troubleshooting guide
- [ ] Test runbooks with team
- [ ] Update based on feedback

**Acceptance Criteria:**

- ✅ Runbooks cover common scenarios
- ✅ Team can follow runbooks successfully
- ✅ Runbooks tested in staging

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.5.3: Create Developer Onboarding Guide

- [ ] Write onboarding guide:
  - [ ] Local development setup
  - [ ] Running tests
  - [ ] Code style guide
  - [ ] Git workflow
  - [ ] How to add new features
  - [ ] How to train models
- [ ] Create video walkthrough (optional)
- [ ] Test with new developer

**Acceptance Criteria:**

- ✅ New developer can set up in < 2 hours
- ✅ Guide covers all common tasks
- ✅ Feedback incorporated

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## 4.6 Security & Compliance

### Task 4.6.1: Implement Security Best Practices

- [ ] API security:
  - [ ] API key authentication
  - [ ] Rate limiting (100 requests/minute)
  - [ ] Input validation and sanitization
  - [ ] SQL injection prevention (use ORM)
- [ ] Data security:
  - [ ] Encrypt data at rest
  - [ ] Encrypt data in transit (HTTPS)
  - [ ] Secure database credentials (environment variables)
- [ ] Run security audit (OWASP checklist)

**Acceptance Criteria:**

- ✅ Security measures implemented
- ✅ No critical vulnerabilities found
- ✅ Audit checklist completed

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

### Task 4.6.2: Implement Responsible Gambling Features

- [ ] Add disclaimers:
  - [ ] "Predictions are not guarantees"
  - [ ] "Gambling involves risk"
  - [ ] "Bet responsibly"
- [ ] Add links to gambling support:
  - [ ] National Council on Problem Gambling
  - [ ] Gamblers Anonymous
- [ ] Add age verification (18+)
- [ ] Document responsible gambling policy

**Acceptance Criteria:**

- ✅ Disclaimers visible on all pages
- ✅ Support resources easily accessible
- ✅ Policy documented

**Status:** 🔴 Not Started  
**Assigned To:** ******\_******  
**Completion Date:** ******\_******

---

## Phase 4 Completion Checklist

**Production readiness:**

- [ ] ✅ MLOps infrastructure operational
- [ ] ✅ Monitoring and alerting configured
- [ ] ✅ A/B testing framework working
- [ ] ✅ Production environment deployed
- [ ] ✅ CI/CD pipeline functional
- [ ] ✅ Documentation complete
- [ ] ✅ Security audit passed
- [ ] ✅ Responsible gambling features implemented
- [ ] ✅ All Phase 4 tests passing

**Phase 4 Sign-Off:**

- [ ] Technical Lead Approval: ******\_****** Date: ******\_******
- [ ] Security Review Completed: ******\_****** Date: ******\_******
- [ ] Production Launch Approved: ☐ Yes ☐ No

---

# ONGOING MAINTENANCE & IMPROVEMENT

## Weekly Tasks

- [ ] Review model performance metrics
- [ ] Check for data quality issues
- [ ] Review error logs
- [ ] Update training data

## Monthly Tasks

- [ ] Retrain all player models
- [ ] Review feature importance
- [ ] Analyze prediction errors
- [ ] Update documentation
- [ ] Review and optimize costs

## Quarterly Tasks

- [ ] Comprehensive model evaluation
- [ ] Feature engineering review
- [ ] Architecture review
- [ ] Security audit
- [ ] User feedback analysis
- [ ] Roadmap planning for next quarter

---

# APPENDIX: Quick Reference

## Key Metrics Targets

| Metric                     | Target  | Current | Status |
| -------------------------- | ------- | ------- | ------ |
| Prediction Accuracy        | 70-85%  | -       | 🔴     |
| Brier Score                | < 0.18  | -       | 🔴     |
| Expected Calibration Error | < 0.10  | -       | 🔴     |
| Backtesting ROI            | > 15%   | -       | 🔴     |
| Prediction Latency         | < 200ms | -       | 🔴     |
| API Uptime                 | > 99.5% | -       | 🔴     |

## Contact Information

| Role              | Name       | Email      | Slack      |
| ----------------- | ---------- | ---------- | ---------- |
| Technical Lead    | ****\_**** | ****\_**** | ****\_**** |
| ML Engineer       | ****\_**** | ****\_**** | ****\_**** |
| Backend Engineer  | ****\_**** | ****\_**** | ****\_**** |
| Frontend Engineer | ****\_**** | ****\_**** | ****\_**** |
| DevOps Engineer   | ****\_**** | ****\_**** | ****\_**** |

## Useful Commands

```bash
# Start backend server
cd backend && uvicorn main:app --reload --port 8000

# Run training pipeline
python backend/training/train_models.py

# Run tests
pytest backend/tests/

# Check code quality
flake8 backend/
black backend/
mypy backend/

# Database migrations
alembic upgrade head

# Start MLflow UI
mlflow ui --port 5000
```

## Important Links

- **GitHub Repository:** [https://github.com/itzcole03/StatMusePicksv2](https://github.com/itzcole03/StatMusePicksv2)
- **MLflow UI:** http://localhost:5000
- **API Documentation:** http://localhost:8000/docs
- **Monitoring Dashboard:** [TBD]
- **Slack Channel:** [TBD]

---

**End of Roadmap**

_This document should be updated regularly as tasks are completed and new requirements emerge._

## UPDATE LOG: Recent Progress & Next Steps (Nov 10, 2025)

- **Progress snapshot:** Backend foundation work advanced — local Postgres + Redis provisioned via `docker-compose.dev.yml`, Alembic migrations applied to Postgres, Redis connectivity verified, `ModelRegistry` added, `MLPredictionService` implemented and `/api/predict` wired and smoke-tested in-process. Frontend test coverage and `aiService.v2` integration validated earlier in the day.
- **What we completed today:**

  - Provisioned Postgres and Redis (Docker Compose) and applied Alembic `0001_initial` migration to the Postgres instance.
  - Implemented and added `backend/services/model_registry.py` and verified metadata persistence schema (`model_metadata` table present).
  - Implemented `backend/services/ml_prediction_service.py` and exposed `/api/predict` and `/api/batch_predict` endpoints; validated with in-process TestClient and local scripts.
  - Added async Redis helper (`backend/services/cache.py`), increased TTL for player context to 6 hours, and added `/debug/status` endpoint for quick infra checks.

  - Added unit test for ML prediction fallback and ensured backend tests run locally (`backend/tests/test_ml_prediction_service_fallback.py`).
  - Fixed Alembic index migration to create index on `player_stats(player_id, game_date)` and corrected downgrade handling (`backend/alembic/versions/0003_add_indexes.py`).
  - Added small dev helper to persist a toy model for tests: `backend/scripts/persist_toy_model.py` (creates `backend/models_store/LeBron_James.pkl`).
  - Installed missing test dependency `aiosqlite` for sqlite-based DB health tests in local dev.
  - Confirmed backend tests pass locally: `python -m pytest backend/tests` → 62 passed (0 failures).

  Additional recent work (Nov 12, 2025):

  - Persisted a toy RandomForest model using the updated feature pipeline (script `backend/scripts/train_and_persist_real_model.py`). Model saved to `backend/models_store/LeBron_James.pkl` and feature list recorded in the training output.

- **Immediate next steps (recommended):**
 - **Immediate next steps (recommended):**

  1. (Done locally) Persisted toy model via `backend/scripts/persist_toy_model.py` to exercise model save/load and enable `ModelRegistry` tests.
  2. Start the FastAPI app pointing at the Postgres + Redis stack and test `/api/predict` end-to-end over HTTP (recommend running in dev: `npm run backend:dev` or `uvicorn backend.main:app --reload --port 8000`).
  3. Add CI job step to run `pytest backend/tests/` as part of backend CI (suggest adding to `backend-ci.yml` or extending `alembic_migration_smoke.yml`).

- **Notes / Caveats:**
  - Alembic expects a sync DB URL when executed as a CLI process; migrations were applied using a `postgresql://` URL (sync driver). The runtime app continues to use the async URL (`postgresql+asyncpg://`) where appropriate.
  - Some roadmap checklist items remain intentionally broad (TimescaleDB, commercial data integrations, full training pipeline). Those are next-phase tasks and will be scheduled after we persist a first model and confirm end-to-end flows.

If you'd like, I can proceed with step 1 now (train & persist a toy model) — reply with: `A` = Persist toy model, `B` = Start FastAPI and run end-to-end request, or `C` = Add unit tests + CI integration now.
