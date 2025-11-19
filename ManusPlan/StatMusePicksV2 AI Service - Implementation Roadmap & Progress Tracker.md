# StatMusePicksV2 AI Service - Implementation Roadmap & Progress Tracker

**Version:** 2.0 (Updated with AI Partner Progress & Command-Line Instructions)
**Last Updated:** November 17, 2025
**Estimated Timeline:** 6-9 months
**Status:** 🟡 In Progress

---

## 📊 Overall Progress Tracker

| Phase | Status | Progress | Start Date | End Date | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1: Foundation** | 🟢 Completed | 100% | - | - | Backend & Data Infrastructure |
| **Phase 2: Core ML** | 🟡 In Progress | 80% | - | - | Per-Player Models & Calibration (High-priority tasks remaining) |
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
**Status:** 🟢 Completed
**Progress:** 25/25 tasks completed

*(All tasks in Phase 1 are validated complete. See previous report for details.)*

---

# PHASE 2: CORE ML MODELS & CALIBRATION (2-3 Months)

**Objective:** Implement per-player ML models with proper calibration
**Status:** 🟡 In Progress
**Progress:** 80% (Core scaffolding complete, execution and validation pending)

## 2.1 Model Training Infrastructure

### Task 2.1.1: Set Up Training Data Pipeline

**Status:** 🟡 In Progress (Scaffold exists, execution pending)

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Data Volume Sync** | 🔴 Pending | **1. Run Multi-Season Data Ingestion (Dry Run):**<br> `export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'`<br> `export SEASONS='2024-25,2023-24,2022-23,2021-22'`<br> `export DRY_RUN='1'`<br> `export NBA_FALLBACK_LIMIT='200'`<br> `python ./scripts/sync_full_nba_db.py`<br>**2. Review Audit:** Verify batch counts and outlier logs. | ✅ `sync_full_nba_db.py` runs without error in dry-run mode. ✅ Audit files show sufficient data batches. |
| **Persist Data** | 🔴 Pending | **3. Run Persisted Ingestion:**<br> `export DRY_RUN='0'`<br> `python ./scripts/sync_full_nba_db.py`<br>**4. Verify Data Adequacy:**<br> `python ./scripts/verify_db_stats.py` (Check player_stats count)<br> **SQL Check:** `SELECT player_id, COUNT(*) FROM player_stats GROUP BY player_id HAVING COUNT(*) >= 50;` (Must return 50+ players) | ✅ DB populated with multi-season team/player history. ✅ 50+ players have $\ge 50$ historical game rows. |
| **Time-Based Split** | 🔴 Pending | **5. Implement Time-Based Split:** Modify `training_data_service.py` to implement a time-based split (70/15/15) on the dataset generated from the DB query. | ✅ Training pipeline uses time-based split (no data leakage). |
| **Data Versioning** | 🔴 Pending | **6. Implement Data Versioning:** Modify `training_data_service.py` to save the split datasets to versioned Parquet files (e.g., `backend/data/datasets/{dataset_version}.parquet`). | ✅ Parquet exports saved under versioned directory. |

### Task 2.1.2: Implement Model Registry

**Status:** 🟢 Completed (No further action required)

### Task 2.1.3: Create Training Pipeline

**Status:** 🟡 In Progress (Scaffold exists, execution pending)

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Orchestrator Execution** | 🔴 Pending | **1. Run Training Orchestrator:**<br> `export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'`<br> `python backend/scripts/train_orchestrator.py` (Ensure this script iterates over players with $\ge 50$ games) | ✅ 50+ player models persisted in `models_store/` with metadata in `model_metadata` DB table. |
| **Hyperparameter Tuning** | 🔴 Pending | **2. Implement Optuna:** Integrate Optuna into `training_pipeline.py` to tune hyperparameters for the RandomForest model. | ✅ Hyperparameter search space defined and executed. |

## 2.2 Model Implementation

### Task 2.2.1: Implement Random Forest Model

**Status:** 🟢 Completed (Core implemented, tuning pending in 2.1.3)

### Task 2.2.2: Implement XGBoost Model

**Status:** 🔴 Not Started

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **XGBoost Integration** | 🔴 Pending | **1. Implement XGBoost:** Add `XGBRegressor` to `training_pipeline.py` with early stopping logic. | ✅ XGBoost model trains successfully (if dependency is installed). |

### Task 2.2.3: Implement ElasticNet Model

**Status:** 🔴 Not Started

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **ElasticNet Integration** | 🔴 Pending | **1. Implement ElasticNet:** Add `ElasticNet` to `training_pipeline.py` as a baseline model. | ✅ ElasticNet model trains successfully. |

### Task 2.2.4: Implement Ensemble Model

**Status:** 🟡 In Progress (Scaffold exists, full model types pending)

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Ensemble Stacking** | 🔴 Pending | **1. Implement Stacking:** Modify `training_pipeline.py` to use `VotingRegressor` with the three completed models (RF, XGB, EN) and implement a simple stacking ensemble. | ✅ Ensemble model is built and compared against baselines. |

## 2.3 Model Evaluation & Calibration

### Task 2.3.1: Implement Calibration Service

**Status:** 🟢 Completed (Isotonic calibrator implemented)

### Task 2.3.2: Implement Calibration Metrics

**Status:** 🔴 Not Started

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Metrics Calculation** | 🔴 Pending | **1. Implement Metrics:** Create a module (e.g., `evaluation_metrics.py`) to compute **Brier Score** and **Expected Calibration Error (ECE)**. | ✅ Scripts compute Brier/ECE on validation sets. |
| **Reliability Diagrams** | 🔴 Pending | **2. Generate Plots:** Add a function to generate and save reliability diagrams for all trained models. | ✅ Reliability diagrams are generated and saved to `backend/reports/`. |
| **Metric Check** | 🔴 Pending | **3. CI Check:** Integrate Brier Score check into the CI/CD pipeline (e.g., `if Brier_Score > 0.20: fail_build()`). | ✅ CI checks metric thresholds for signoff. |

### Task 2.3.3: Implement Backtesting Engine

**Status:** 🔴 Not Started

| Sub-Task | Status | Exact Instruction for AI Partner | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **Backtesting Framework** | 🔴 Pending | **1. Implement Backtesting:** Create `backend/scripts/backtesting.py` to simulate betting strategy on the test set. | ✅ Backtest engine simulates betting strategy. |
| **ROI Validation** | 🔴 Pending | **2. Validate ROI:** Run backtest and ensure the reported **Return on Investment (ROI) is $\ge 5\%$** on the historical test data. | ✅ Backtesting report shows ROI $\ge 5\%$. |

---

# PHASE 3: ADVANCED FEATURES (2-3 Months)

**Objective:** Implement advanced feature engineering and MLOps
**Status:** 🔴 Not Started

*(All tasks in Phase 3 remain as originally planned, focusing on advanced feature creation and LLM integration.)*

---

# PHASE 4: PRODUCTION & MLOPS (Ongoing)

**Objective:** Deploy, monitor, and automate the ML pipeline
**Status:** 🔴 Not Started

*(All tasks in Phase 4 remain as originally planned, focusing on production readiness.)*
