# StatMusePicksV2 AI Service - Implementation Roadmap & Progress Tracker

**Version:** 1.0  
**Last Updated:** November 10, 2025  
**Estimated Timeline:** 6-9 months  
**Status:** 🟡 In Progress

---

## 📊 Overall Progress Tracker

| Phase | Status | Progress | Start Date | End Date | Notes |
|-------|--------|----------|------------|----------|-------|
| **Phase 1: Foundation** | 🟡 In Progress | 8% | - | - | Backend & Data Infrastructure |
| **Phase 2: Core ML** | 🔴 Not Started | 0% | - | - | Per-Player Models & Calibration |
| **Phase 3: Advanced Features** | 🔴 Not Started | 0% | - | - | Feature Engineering & Ensemble |
| **Phase 4: Production** | 🔴 Not Started | 0% | - | - | MLOps & Automation |

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
**Progress:** 14/25 tasks completed

### Recent Progress (Nov 10, 2025)
- [x] Wired `aiService.v2` into the frontend analysis pipeline and UI.
- [x] Added E2E component test comparing LLM output with statistical evidence (`src/components/__tests__/AnalysisSection.e2e.test.tsx`).
- [x] Executed frontend E2E test locally (vitest) to verify agreement flow and UI behavior.
- [x] Added backend `ModelRegistry` and `ModelMetadata` model; `ModelRegistry.save_model` persists metadata.
- [x] Added Alembic migrations and initial `0001_initial` migration including `model_metadata` table.
- [x] Implemented ML prediction scaffold and model management endpoints (`/api/models`, `/api/models/load`, `/api/predict`).
- [x] Added integration test `tests/test_model_metadata.py` that runs migrations and training example to verify metadata insertion.
- [x] Added deterministic disagreement handling using `aiService.v2` to flag and null LLM recommendations when v2 strongly disagrees.
- [x] Added an E2E disagreement test `src/components/__tests__/AnalysisSection.disagreement.e2e.test.tsx` that verifies flagging behavior.

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
**Assigned To:** _____________  
**Completion Date:** _____________

---

### Task 1.1.2: Set Up Database Infrastructure
- [ ] Install PostgreSQL 14+ locally or provision cloud instance
- [ ] Create database: `statmuse_predictions`
- [ ] Install TimescaleDB extension for time-series data
- [ ] Create database schema:
  - [ ] `players` table (id, name, team, position, etc.)
  - [ ] `games` table (id, date, home_team, away_team, etc.)
  - [ ] `player_stats` table (player_id, game_id, stat_type, value, date)
  - [ ] `predictions` table (id, player_id, stat_type, predicted_value, actual_value, date)
  - [ ] `models` table (id, player_id, model_type, version, created_at)
- [ ] Set up database migrations (Alembic)
- [ ] Create database connection pool in FastAPI

**Acceptance Criteria:**
- ✅ Database accessible from backend
- ✅ All tables created with proper indexes
- ✅ Can insert and query test data

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

---

### Task 1.1.3: Set Up Redis Cache
- [ ] Install Redis locally or provision cloud instance
- [ ] Configure Redis connection in backend
- [ ] Implement caching layer for:
  - [ ] Player context data (TTL: 6 hours)
  - [ ] Opponent stats (TTL: 24 hours)
  - [ ] Model predictions (TTL: 1 hour)
- [ ] Create cache invalidation logic
- [ ] Test cache hit/miss scenarios

**Acceptance Criteria:**
- ✅ Redis accessible from backend
- ✅ Cache stores and retrieves data correctly
- ✅ TTL expiration works as expected

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

---

## 1.2 Data Source Integration

### Task 1.2.1: Integrate NBA Stats API
- [ ] Research NBA Stats API endpoints
- [ ] Create `backend/services/nba_stats_client.py`
- [ ] Implement functions:
  - [ ] `get_player_info(player_name)` → player ID, team, position
  - [ ] `get_player_game_log(player_id, season)` → recent games
  - [ ] `get_player_season_stats(player_id, season)` → season averages
  - [ ] `get_team_stats(team_id)` → team offensive/defensive ratings
- [ ] Add rate limiting (max 20 requests/minute)
- [ ] Add retry logic with exponential backoff
- [ ] Test with 5 different players

**Acceptance Criteria:**
- ✅ Successfully fetches data for test players
- ✅ Rate limiting prevents API abuse
- ✅ Handles API errors gracefully

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

---

### Task 1.2.2: Integrate Commercial Sports Data API (Optional but Recommended)
- [ ] Evaluate sports data providers:
  - [ ] Sportradar (recommended)
  - [ ] Stats Perform
  - [ ] The Odds API
- [ ] Sign up for API access (may require paid plan)
- [ ] Create `backend/services/sports_data_client.py`
- [ ] Implement functions:
  - [ ] `get_advanced_player_stats(player_id)` → PER, TS%, USG%, PIE
  - [ ] `get_opponent_defensive_stats(team_id)` → defensive rating, pace
  - [ ] `get_injury_reports()` → current injuries
  - [ ] `get_betting_lines(game_id)` → current odds
- [ ] Test with real API credentials

**Acceptance Criteria:**
- ✅ API credentials configured
- ✅ Successfully fetches advanced metrics
- ✅ Data format validated

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

---

### Task 1.2.3: Build Data Ingestion Pipeline
- [ ] Create `backend/services/data_ingestion_service.py`
- [ ] Implement daily data sync:
  - [ ] Fetch yesterday's game results
  - [ ] Update player stats in database
  - [ ] Update team stats
  - [ ] Store raw data for auditing
- [ ] Add data validation:
  - [ ] Check for missing values
  - [ ] Detect outliers (e.g., stat > 3 std deviations)
  - [ ] Validate data types
- [ ] Create scheduled job (cron or Celery):
  - [ ] Run daily at 6 AM EST (after games finish)
- [ ] Add logging and error notifications

**Acceptance Criteria:**
- ✅ Pipeline runs without manual intervention
- ✅ Data validation catches errors
- ✅ Failed jobs send alerts

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

---

## 1.3 Feature Engineering Pipeline

### Task 1.3.1: Implement Basic Feature Engineering
- [ ] Create `backend/services/feature_engineering.py`
- [ ] Implement `FeatureEngineering` class
- [ ] Add basic features:
  - [ ] Recent performance (last 3, 5, 10 games averages)
  - [ ] Season average
  - [ ] Home/away indicator
  - [ ] Days of rest
  - [ ] Back-to-back game indicator
- [ ] Create feature extraction function:
  - [ ] Input: player_id, game_date
  - [ ] Output: feature DataFrame
- [ ] Test with 10 different players

**Acceptance Criteria:**
- ✅ Features calculated correctly
- ✅ Handles missing data gracefully
- ✅ Returns consistent DataFrame schema

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

---

### Task 1.3.2: Add Rolling Statistics
- [ ] Implement rolling averages:
  - [ ] Simple Moving Average (SMA) for 3, 5, 10 games
  - [ ] Exponential Moving Average (EMA) with alpha=0.3
  - [ ] Weighted Moving Average (recent games weighted higher)
- [ ] Implement rolling statistics:
  - [ ] Rolling standard deviation
  - [ ] Rolling min/max
  - [ ] Rolling median
- [ ] Add trend detection:
  - [ ] Linear regression slope over last 10 games
  - [ ] Momentum indicator (current vs 5-game avg)
- [ ] Test on historical data

**Acceptance Criteria:**
- ✅ Rolling calculations match manual verification
- ✅ Handles edge cases (< 3 games available)
- ✅ Performance acceptable (< 100ms per player)

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

---

### Task 1.4.2: Create Batch Context Endpoint
- [ ] Implement `/api/batch_player_context` endpoint
- [ ] Accept list of player requests
- [ ] Process in parallel (asyncio)
- [ ] Return list of player contexts
- [ ] Add rate limiting (max 50 players per request)
- [ ] Optimize database queries (batch fetch)

**Acceptance Criteria:**
- ✅ Handles 50 players in < 3 seconds
- ✅ Returns partial results if some players fail
- ✅ Rate limiting works correctly

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

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

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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

- [ ] Technical Lead Approval: _____________ Date: _____________
- [ ] Code Review Completed: _____________ Date: _____________
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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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

**Status:** 🔴 Not Started  
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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

- [ ] Technical Lead Approval: _____________ Date: _____________
- [ ] Code Review Completed: _____________ Date: _____________
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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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

- [ ] Technical Lead Approval: _____________ Date: _____________
- [ ] Code Review Completed: _____________ Date: _____________
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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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
**Assigned To:** _____________  
**Completion Date:** _____________

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

- [ ] Technical Lead Approval: _____________ Date: _____________
- [ ] Security Review Completed: _____________ Date: _____________
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

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Prediction Accuracy | 70-85% | - | 🔴 |
| Brier Score | < 0.18 | - | 🔴 |
| Expected Calibration Error | < 0.10 | - | 🔴 |
| Backtesting ROI | > 15% | - | 🔴 |
| Prediction Latency | < 200ms | - | 🔴 |
| API Uptime | > 99.5% | - | 🔴 |

## Contact Information

| Role | Name | Email | Slack |
|------|------|-------|-------|
| Technical Lead | _________ | _________ | _________ |
| ML Engineer | _________ | _________ | _________ |
| Backend Engineer | _________ | _________ | _________ |
| Frontend Engineer | _________ | _________ | _________ |
| DevOps Engineer | _________ | _________ | _________ |

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

*This document should be updated regularly as tasks are completed and new requirements emerge.*
