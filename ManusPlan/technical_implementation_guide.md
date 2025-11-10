# Technical Implementation Guide: Detailed Specifications

**Author:** Manus AI

**Date:** November 10, 2025

## 1. Detailed Code-Level Improvements

This section provides specific, actionable recommendations for improving the existing codebase with concrete code examples and implementation strategies.

### 1.1. Enhanced aiService.ts

The current `aiService.ts` relies entirely on LLM prompt engineering. We recommend refactoring this service to act as an orchestrator that coordinates multiple prediction sources.

#### Current Limitations:

The current implementation has several issues:

1. **Simple heuristic scoring** (lines 203-215 in `aiService.ts`): Uses a naive comparison of `trustedAvg` vs `line` without considering variance, trend, or confidence intervals.
2. **No statistical significance testing**: Doesn't account for sample size or statistical power.
3. **Binary recommendations**: Only outputs OVER/UNDER without probability estimates.
4. **No ensemble approach**: Single model prediction without aggregation.

#### Recommended Refactoring:

```typescript
// NEW: Enhanced prediction interface
interface PredictionResult {
  player: string;
  stat: string;
  line: number;
  
  // Probability-based predictions
  overProbability: number;  // 0-1 probability of going OVER
  underProbability: number; // 0-1 probability of going UNDER
  
  // Calibrated confidence
  calibratedConfidence: number; // 0-100, calibrated score
  
  // Model ensemble
  modelPredictions: {
    randomForest: number;
    xgboost: number;
    elasticNet: number;
    llmQualitative: number;
  };
  
  // Statistical evidence
  evidence: {
    mean: number;
    median: number;
    std: number;
    trendSlope: number;  // Linear regression slope of recent games
    confidenceInterval: [number, number]; // 95% CI
    sampleSize: number;
  };
  
  // Final recommendation
  recommendation: 'OVER' | 'UNDER' | null;
  expectedValue: number; // EV calculation
}

// NEW: Statistical analysis functions
export function calculateStatisticalEvidence(
  recentGames: number[],
  seasonAvg: number | null
): PredictionResult['evidence'] {
  if (!recentGames || recentGames.length === 0) {
    return null;
  }
  
  const mean = recentGames.reduce((a, b) => a + b, 0) / recentGames.length;
  const sortedGames = [...recentGames].sort((a, b) => a - b);
  const median = sortedGames[Math.floor(sortedGames.length / 2)];
  
  // Calculate standard deviation
  const variance = recentGames.reduce((sum, val) => 
    sum + Math.pow(val - mean, 2), 0) / recentGames.length;
  const std = Math.sqrt(variance);
  
  // Calculate trend using simple linear regression
  const n = recentGames.length;
  const xMean = (n - 1) / 2;
  const numerator = recentGames.reduce((sum, y, x) => 
    sum + (x - xMean) * (y - mean), 0);
  const denominator = recentGames.reduce((sum, _, x) => 
    sum + Math.pow(x - xMean, 2), 0);
  const trendSlope = numerator / denominator;
  
  // 95% confidence interval (assuming normal distribution)
  const marginOfError = 1.96 * (std / Math.sqrt(n));
  const confidenceInterval: [number, number] = [
    mean - marginOfError,
    mean + marginOfError
  ];
  
  return {
    mean,
    median,
    std,
    trendSlope,
    confidenceInterval,
    sampleSize: n
  };
}

// NEW: Expected Value calculation
export function calculateExpectedValue(
  overProbability: number,
  line: number,
  oddsOver: number = -110,  // Standard American odds
  oddsUnder: number = -110
): number {
  // Convert American odds to decimal
  const decimalOddsOver = oddsOver > 0 
    ? (oddsOver / 100) + 1 
    : (100 / Math.abs(oddsOver)) + 1;
  const decimalOddsUnder = oddsUnder > 0 
    ? (oddsUnder / 100) + 1 
    : (100 / Math.abs(oddsUnder)) + 1;
  
  // Calculate EV for betting OVER
  const evOver = (overProbability * decimalOddsOver) - 1;
  
  // Calculate EV for betting UNDER
  const underProbability = 1 - overProbability;
  const evUnder = (underProbability * decimalOddsUnder) - 1;
  
  // Return the better EV
  return Math.max(evOver, evUnder);
}
```

### 1.2. Enhanced nbaService.ts

The current `nbaService.ts` is a stub that needs to be replaced with a robust data fetching service.

#### Recommended Implementation:

```typescript
// NEW: Comprehensive data fetching service
export interface EnhancedPlayerContext extends NBAPlayerContext {
  // Advanced metrics
  advancedMetrics: {
    per: number | null;           // Player Efficiency Rating
    ts_pct: number | null;        // True Shooting %
    usg_pct: number | null;       // Usage Rate %
    pie: number | null;           // Player Impact Estimate
    offRating: number | null;     // Offensive Rating
    defRating: number | null;     // Defensive Rating
  };
  
  // Rolling averages
  rollingAverages: {
    last3Games: number | null;
    last5Games: number | null;
    last10Games: number | null;
    exponentialMovingAvg: number | null;
  };
  
  // Contextual factors
  contextualFactors: {
    homeAway: 'home' | 'away' | null;
    daysRest: number | null;
    isBackToBack: boolean;
    travelDistance: number | null;
  };
  
  // Opponent-adjusted stats
  opponentAdjusted: {
    avgVsTop10Defenses: number | null;
    avgVsBottom10Defenses: number | null;
    avgVsSimilarOpponent: number | null;
  };
  
  // Historical matchup data
  historicalMatchup: {
    gamesVsOpponent: number;
    avgVsOpponent: number | null;
    lastGameVsOpponent: {
      date: string;
      statValue: number;
    } | null;
  };
}

// NEW: Feature engineering pipeline
export async function buildEnhancedFeatures(
  proj: ParsedProjection,
  settings: Settings
): Promise<EnhancedPlayerContext | null> {
  // Fetch raw data from multiple sources
  const [
    basicContext,
    advancedStats,
    opponentData,
    matchupHistory
  ] = await Promise.all([
    fetchPlayerContextFromNBA(proj, settings),
    fetchAdvancedPlayerStats(proj.player, settings),
    fetchOpponentDefensiveStats(proj.team, settings),
    fetchHistoricalMatchup(proj.player, proj.team, settings)
  ]);
  
  if (!basicContext) return null;
  
  // Calculate rolling averages
  const rollingAverages = calculateRollingAverages(
    basicContext.recentGames
  );
  
  // Calculate opponent-adjusted stats
  const opponentAdjusted = calculateOpponentAdjustedStats(
    basicContext.recentGames,
    opponentData
  );
  
  return {
    ...basicContext,
    advancedMetrics: advancedStats,
    rollingAverages,
    contextualFactors: {
      homeAway: determineHomeAway(proj),
      daysRest: calculateDaysRest(basicContext.recentGames),
      isBackToBack: isBackToBackGame(basicContext.recentGames),
      travelDistance: null // Requires additional data source
    },
    opponentAdjusted,
    historicalMatchup: matchupHistory
  };
}

function calculateRollingAverages(
  recentGames: Array<{date: string, statValue: number}>
): EnhancedPlayerContext['rollingAverages'] {
  if (!recentGames || recentGames.length === 0) {
    return {
      last3Games: null,
      last5Games: null,
      last10Games: null,
      exponentialMovingAvg: null
    };
  }
  
  const values = recentGames.map(g => g.statValue);
  
  const last3 = values.slice(0, 3);
  const last5 = values.slice(0, 5);
  const last10 = values.slice(0, 10);
  
  // Exponential moving average with alpha = 0.3
  const alpha = 0.3;
  let ema = values[0];
  for (let i = 1; i < values.length; i++) {
    ema = alpha * values[i] + (1 - alpha) * ema;
  }
  
  return {
    last3Games: last3.length >= 3 
      ? last3.reduce((a, b) => a + b, 0) / last3.length 
      : null,
    last5Games: last5.length >= 5 
      ? last5.reduce((a, b) => a + b, 0) / last5.length 
      : null,
    last10Games: last10.length >= 10 
      ? last10.reduce((a, b) => a + b, 0) / last10.length 
      : null,
    exponentialMovingAvg: ema
  };
}
```

### 1.3. New Model Service (Python Backend)

The most critical improvement is to add a Python backend that handles the machine learning models.

#### Recommended Architecture:

```python
# backend/services/ml_prediction_service.py

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from xgboost import XGBRegressor
from sklearn.linear_model import ElasticNet
from sklearn.isotonic import IsotonicRegression
import joblib
import logging

logger = logging.getLogger(__name__)

class PlayerModelRegistry:
    """
    Registry that maintains individual models for each player.
    """
    def __init__(self, model_dir: str = "./models"):
        self.model_dir = model_dir
        self.player_models: Dict[str, VotingRegressor] = {}
        self.calibrators: Dict[str, IsotonicRegression] = {}
        
    def get_or_train_model(
        self, 
        player_name: str, 
        training_data: pd.DataFrame
    ) -> VotingRegressor:
        """
        Get existing model or train a new one for the player.
        """
        if player_name in self.player_models:
            return self.player_models[player_name]
        
        # Train new ensemble model
        model = self._train_ensemble_model(training_data)
        self.player_models[player_name] = model
        
        # Save model to disk
        model_path = f"{self.model_dir}/{player_name.replace(' ', '_')}.pkl"
        joblib.dump(model, model_path)
        
        return model
    
    def _train_ensemble_model(
        self, 
        training_data: pd.DataFrame
    ) -> VotingRegressor:
        """
        Train an ensemble of models for a single player.
        """
        X = training_data.drop(['target', 'player'], axis=1)
        y = training_data['target']
        
        # Define base models
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        
        xgb = XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
        
        elastic = ElasticNet(
            alpha=0.1,
            l1_ratio=0.5,
            random_state=42
        )
        
        # Create voting ensemble
        ensemble = VotingRegressor(
            estimators=[
                ('rf', rf),
                ('xgb', xgb),
                ('elastic', elastic)
            ],
            weights=[0.4, 0.4, 0.2]  # Weight XGBoost and RF higher
        )
        
        ensemble.fit(X, y)
        
        return ensemble
    
    def calibrate_model(
        self,
        player_name: str,
        validation_data: pd.DataFrame
    ):
        """
        Apply isotonic regression for probability calibration.
        """
        model = self.player_models.get(player_name)
        if not model:
            raise ValueError(f"No model found for {player_name}")
        
        X_val = validation_data.drop(['target', 'player'], axis=1)
        y_val = validation_data['target']
        
        # Get raw predictions
        raw_predictions = model.predict(X_val)
        
        # Fit isotonic regression
        calibrator = IsotonicRegression(out_of_bounds='clip')
        calibrator.fit(raw_predictions, y_val)
        
        self.calibrators[player_name] = calibrator
        
        # Save calibrator
        calibrator_path = f"{self.model_dir}/{player_name.replace(' ', '_')}_calibrator.pkl"
        joblib.dump(calibrator, calibrator_path)

class FeatureEngineering:
    """
    Feature engineering pipeline for NBA player predictions.
    """
    
    @staticmethod
    def engineer_features(
        player_data: Dict,
        opponent_data: Dict
    ) -> pd.DataFrame:
        """
        Transform raw player and opponent data into ML features.
        """
        features = {}
        
        # Recent performance features
        recent_games = player_data.get('recentGames', [])
        if recent_games:
            values = [g['statValue'] for g in recent_games if g.get('statValue') is not None]
            
            if values:
                features['recent_mean'] = np.mean(values)
                features['recent_median'] = np.median(values)
                features['recent_std'] = np.std(values)
                features['recent_min'] = np.min(values)
                features['recent_max'] = np.max(values)
                
                # Rolling averages
                features['last_3_avg'] = np.mean(values[:3]) if len(values) >= 3 else None
                features['last_5_avg'] = np.mean(values[:5]) if len(values) >= 5 else None
                features['last_10_avg'] = np.mean(values[:10]) if len(values) >= 10 else None
                
                # Trend (linear regression slope)
                if len(values) >= 3:
                    x = np.arange(len(values))
                    slope, _ = np.polyfit(x, values, 1)
                    features['trend_slope'] = slope
                
                # Volatility (coefficient of variation)
                features['volatility'] = np.std(values) / np.mean(values) if np.mean(values) > 0 else 0
        
        # Season average
        features['season_avg'] = player_data.get('seasonAvg')
        
        # Advanced metrics
        adv_metrics = player_data.get('advancedMetrics', {})
        features['per'] = adv_metrics.get('per')
        features['ts_pct'] = adv_metrics.get('ts_pct')
        features['usg_pct'] = adv_metrics.get('usg_pct')
        features['pie'] = adv_metrics.get('pie')
        
        # Opponent features
        opponent = opponent_data or {}
        features['opp_def_rating'] = opponent.get('defensiveRating')
        features['opp_pace'] = opponent.get('pace')
        
        # Projected minutes
        features['projected_minutes'] = player_data.get('projectedMinutes')
        
        # Contextual features
        context = player_data.get('contextualFactors', {})
        features['is_home'] = 1 if context.get('homeAway') == 'home' else 0
        features['days_rest'] = context.get('daysRest')
        features['is_back_to_back'] = 1 if context.get('isBackToBack') else 0
        
        # Convert to DataFrame
        df = pd.DataFrame([features])
        
        # Fill missing values with median (or 0 for now)
        df = df.fillna(0)
        
        return df

class MLPredictionService:
    """
    Main service for ML-based predictions.
    """
    def __init__(self):
        self.model_registry = PlayerModelRegistry()
        self.feature_engineer = FeatureEngineering()
    
    async def predict(
        self,
        player_name: str,
        stat_type: str,
        line: float,
        player_data: Dict,
        opponent_data: Dict
    ) -> Dict:
        """
        Generate ML-based prediction for a player prop.
        """
        try:
            # Engineer features
            features = self.feature_engineer.engineer_features(
                player_data, 
                opponent_data
            )
            
            # Get player model
            model = self.model_registry.player_models.get(player_name)
            if not model:
                logger.warning(f"No trained model for {player_name}, using fallback")
                return self._fallback_prediction(player_data, line)
            
            # Make raw prediction
            raw_prediction = model.predict(features)[0]
            
            # Apply calibration if available
            calibrator = self.model_registry.calibrators.get(player_name)
            if calibrator:
                calibrated_prediction = calibrator.predict([raw_prediction])[0]
            else:
                calibrated_prediction = raw_prediction
            
            # Calculate probability of going OVER
            # Using a simple logistic transformation
            over_probability = 1 / (1 + np.exp(-(calibrated_prediction - line)))
            
            # Calculate expected value (assuming -110 odds)
            ev = self._calculate_ev(over_probability, -110, -110)
            
            # Determine recommendation
            recommendation = 'OVER' if over_probability > 0.55 else 'UNDER'
            if 0.45 <= over_probability <= 0.55:
                recommendation = None  # No clear edge
            
            return {
                'player': player_name,
                'stat': stat_type,
                'line': line,
                'predicted_value': calibrated_prediction,
                'over_probability': over_probability,
                'under_probability': 1 - over_probability,
                'recommendation': recommendation,
                'expected_value': ev,
                'confidence': abs(over_probability - 0.5) * 200  # 0-100 scale
            }
            
        except Exception as e:
            logger.error(f"Error in ML prediction for {player_name}: {e}")
            return self._fallback_prediction(player_data, line)
    
    def _fallback_prediction(self, player_data: Dict, line: float) -> Dict:
        """
        Simple fallback when ML model is unavailable.
        """
        recent_avg = player_data.get('rollingAverages', {}).get('last5Games')
        if recent_avg is None:
            recent_avg = player_data.get('seasonAvg')
        
        if recent_avg is None:
            return {
                'recommendation': None,
                'confidence': 0,
                'over_probability': 0.5
            }
        
        over_prob = 0.5 + (recent_avg - line) * 0.05  # Simple heuristic
        over_prob = max(0.1, min(0.9, over_prob))  # Clip to [0.1, 0.9]
        
        return {
            'predicted_value': recent_avg,
            'over_probability': over_prob,
            'recommendation': 'OVER' if over_prob > 0.55 else 'UNDER',
            'confidence': abs(over_prob - 0.5) * 100
        }
    
    @staticmethod
    def _calculate_ev(
        over_probability: float,
        odds_over: int = -110,
        odds_under: int = -110
    ) -> float:
        """
        Calculate expected value for betting.
        """
        # Convert American odds to decimal
        decimal_over = (100 / abs(odds_over)) + 1 if odds_over < 0 else (odds_over / 100) + 1
        decimal_under = (100 / abs(odds_under)) + 1 if odds_under < 0 else (odds_under / 100) + 1
        
        ev_over = (over_probability * decimal_over) - 1
        ev_under = ((1 - over_probability) * decimal_under) - 1
        
        return max(ev_over, ev_under)
```

### 1.4. FastAPI Backend Endpoints

```python
# backend/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from services.ml_prediction_service import MLPredictionService
import logging

app = FastAPI(title="StatMusePicks ML Backend")
logger = logging.getLogger(__name__)

ml_service = MLPredictionService()

class PredictionRequest(BaseModel):
    player: str
    stat: str
    line: float
    team: str
    opponent: str
    player_data: Dict
    opponent_data: Dict

class PredictionResponse(BaseModel):
    player: str
    stat: str
    line: float
    predicted_value: float
    over_probability: float
    under_probability: float
    recommendation: Optional[str]
    expected_value: float
    confidence: float

@app.post("/predict", response_model=PredictionResponse)
async def predict_prop(request: PredictionRequest):
    """
    Generate ML-based prediction for a player prop.
    """
    try:
        result = await ml_service.predict(
            player_name=request.player,
            stat_type=request.stat,
            line=request.line,
            player_data=request.player_data,
            opponent_data=request.opponent_data
        )
        return PredictionResponse(**result)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch_predict")
async def batch_predict(requests: List[PredictionRequest]):
    """
    Generate predictions for multiple props in batch.
    """
    results = []
    for req in requests:
        try:
            result = await ml_service.predict(
                player_name=req.player,
                stat_type=req.stat,
                line=req.line,
                player_data=req.player_data,
                opponent_data=req.opponent_data
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Error predicting {req.player}: {e}")
            results.append({
                'player': req.player,
                'error': str(e),
                'recommendation': None
            })
    
    return {'predictions': results}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

## 2. Data Pipeline Architecture

### 2.1. Data Sources

**Primary Data Sources:**

1. **NBA Stats API** (free, rate-limited)
   - Basic player stats
   - Team stats
   - Game logs

2. **Commercial Sports Data Provider** (paid, recommended)
   - Sportradar
   - Stats Perform
   - Comprehensive coverage, advanced metrics, real-time updates

3. **Betting Odds Aggregator**
   - Odds API
   - Track line movements
   - Identify market inefficiencies

### 2.2. Data Storage

**Recommended Stack:**

- **PostgreSQL**: Relational data (player info, game schedules)
- **TimescaleDB**: Time-series data (game logs, stats over time)
- **Redis**: Caching layer for frequently accessed data
- **S3/Cloud Storage**: Model artifacts, historical backups

### 2.3. Data Pipeline Flow

```
[Data Sources] 
    ↓
[Data Ingestion Service] (Python/Airflow)
    ↓
[Data Validation & Cleaning]
    ↓
[Feature Engineering Pipeline]
    ↓
[Feature Store] (PostgreSQL/TimescaleDB)
    ↓
[Model Training Pipeline] (Scheduled/On-Demand)
    ↓
[Model Registry] (MLflow)
    ↓
[Prediction API] (FastAPI)
    ↓
[Frontend] (React/TypeScript)
```

## 3. Model Training & Evaluation

### 3.1. Training Data Requirements

**Minimum Requirements:**
- 2-3 seasons of historical data per player
- At least 50 games per player for individual models
- For players with < 50 games, use a global model or ensemble

**Optimal:**
- 5+ seasons of data
- 100+ games per player
- Include playoff games (weighted differently)

### 3.2. Train/Validation/Test Split

**Time-Series Cross-Validation:**

Do NOT use random splits. Use time-based splits to avoid look-ahead bias.

```python
# Example: Rolling window cross-validation
def time_series_cv_split(data, n_splits=5):
    """
    Split data into time-based folds.
    """
    data = data.sort_values('date')
    total_size = len(data)
    fold_size = total_size // (n_splits + 1)
    
    for i in range(n_splits):
        train_end = fold_size * (i + 1)
        val_end = train_end + fold_size
        
        train = data.iloc[:train_end]
        val = data.iloc[train_end:val_end]
        
        yield train, val
```

### 3.3. Evaluation Metrics

**Primary Metrics:**

1. **Brier Score** (lower is better)
   - Measures accuracy of probabilistic predictions
   - Formula: `(1/N) * Σ(predicted_prob - actual_outcome)²`

2. **Expected Calibration Error (ECE)**
   - Measures calibration quality
   - Bins predictions and compares expected vs actual accuracy

3. **ROI (Return on Investment)**
   - Ultimate metric for profitability
   - Simulated betting with Kelly Criterion or fixed stake

**Secondary Metrics:**

- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- Accuracy (for binary OVER/UNDER)

### 3.4. Hyperparameter Tuning

Use Optuna or similar for automated hyperparameter optimization:

```python
import optuna
from sklearn.model_selection import cross_val_score

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 200),
        'max_depth': trial.suggest_int('max_depth', 3, 15),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
    }
    
    model = XGBRegressor(**params)
    score = cross_val_score(model, X_train, y_train, cv=5, scoring='neg_brier_score')
    
    return score.mean()

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)
```

## 4. Monitoring & Maintenance

### 4.1. Model Performance Monitoring

**Key Metrics to Track:**

- Daily prediction accuracy
- Calibration drift over time
- ROI on simulated bets
- Feature importance changes
- Data quality issues (missing values, outliers)

**Alerting Thresholds:**

- Accuracy drops below 60%
- Calibration error exceeds 0.15
- ROI becomes negative for 7+ consecutive days

### 4.2. Model Retraining Schedule

**Recommended Schedule:**

- **Daily**: Update feature store with latest game results
- **Weekly**: Retrain models for high-volume players (30+ games/season)
- **Monthly**: Full retraining for all player models
- **Quarterly**: Review and update feature engineering pipeline

### 4.3. A/B Testing

Implement A/B testing to compare model versions:

```python
class ABTestingService:
    def __init__(self):
        self.model_v1 = load_model('v1')
        self.model_v2 = load_model('v2')
        self.results = {'v1': [], 'v2': []}
    
    def predict(self, player, features):
        # Randomly assign to model version
        version = 'v1' if random.random() < 0.5 else 'v2'
        model = self.model_v1 if version == 'v1' else self.model_v2
        
        prediction = model.predict(features)
        
        # Log for later analysis
        self.log_prediction(version, player, prediction)
        
        return prediction
```

## 5. Security & Compliance

### 5.1. API Security

- Use API keys for authentication
- Rate limiting to prevent abuse
- HTTPS only for all endpoints
- Input validation and sanitization

### 5.2. Data Privacy

- Do not store personal user information
- Anonymize any user interaction logs
- Comply with GDPR/CCPA if applicable

### 5.3. Responsible Gambling

- Display disclaimers about gambling risks
- Provide links to gambling addiction resources
- Do not make guarantees about profitability

## 6. Cost Optimization

### 6.1. Infrastructure Costs

**Estimated Monthly Costs (AWS):**

- **Compute** (EC2/ECS): $100-300/month
- **Database** (RDS PostgreSQL): $50-150/month
- **Storage** (S3): $10-30/month
- **Data API** (Sportradar): $500-2000/month
- **Total**: ~$660-2480/month

### 6.2. Cost Reduction Strategies

1. Use spot instances for model training
2. Implement aggressive caching (Redis)
3. Batch API calls to data providers
4. Use serverless functions for infrequent tasks
5. Optimize database queries and indexes

## 7. Testing Strategy

### 7.1. Unit Tests

Test individual components:

```python
def test_feature_engineering():
    player_data = {
        'recentGames': [
            {'date': '2024-01-01', 'statValue': 25},
            {'date': '2024-01-03', 'statValue': 30},
            {'date': '2024-01-05', 'statValue': 28}
        ],
        'seasonAvg': 27.5
    }
    
    features = FeatureEngineering.engineer_features(player_data, {})
    
    assert features['recent_mean'] == pytest.approx(27.67, 0.01)
    assert features['recent_std'] > 0
    assert features['last_3_avg'] == pytest.approx(27.67, 0.01)
```

### 7.2. Integration Tests

Test end-to-end prediction flow:

```python
@pytest.mark.asyncio
async def test_prediction_endpoint():
    request = PredictionRequest(
        player='LeBron James',
        stat='points',
        line=25.5,
        team='LAL',
        opponent='GSW',
        player_data={...},
        opponent_data={...}
    )
    
    response = await predict_prop(request)
    
    assert response.player == 'LeBron James'
    assert 0 <= response.over_probability <= 1
    assert response.recommendation in ['OVER', 'UNDER', None]
```

### 7.3. Backtesting

Simulate historical betting:

```python
def backtest_strategy(predictions, actual_results, initial_bankroll=1000):
    """
    Backtest a betting strategy using historical predictions.
    """
    bankroll = initial_bankroll
    bets = []
    
    for pred, actual in zip(predictions, actual_results):
        # Only bet if EV > 0 and confidence > 60
        if pred['expected_value'] > 0 and pred['confidence'] > 60:
            stake = bankroll * 0.02  # 2% Kelly
            
            # Determine if bet won
            if pred['recommendation'] == 'OVER':
                won = actual['stat_value'] > pred['line']
            else:
                won = actual['stat_value'] < pred['line']
            
            # Update bankroll
            if won:
                bankroll += stake * 0.91  # -110 odds = 0.91 profit
            else:
                bankroll -= stake
            
            bets.append({
                'stake': stake,
                'won': won,
                'bankroll': bankroll
            })
    
    roi = (bankroll - initial_bankroll) / initial_bankroll * 100
    win_rate = sum(b['won'] for b in bets) / len(bets) * 100
    
    return {
        'final_bankroll': bankroll,
        'roi': roi,
        'win_rate': win_rate,
        'total_bets': len(bets)
    }
```

## 8. Documentation & Knowledge Transfer

### 8.1. Code Documentation

- Use docstrings for all functions and classes
- Include type hints for all parameters
- Provide usage examples in docstrings

### 8.2. System Documentation

Create comprehensive documentation covering:

- Architecture diagrams
- Data flow diagrams
- API documentation (Swagger/OpenAPI)
- Deployment guide
- Troubleshooting guide

### 8.3. Runbook

Create operational runbooks for:

- Model retraining procedures
- Incident response
- Database backup/restore
- Scaling procedures

## 9. Conclusion

This technical implementation guide provides detailed, actionable specifications for transforming the StatMusePicksV2 AI service from a basic LLM-based system to a sophisticated, production-grade machine learning platform. The key to success is a systematic, phased approach that prioritizes data quality, feature engineering, and model calibration over raw model complexity.

By following these recommendations, the service can achieve significantly higher prediction accuracy, better calibration, and ultimately, profitability in sports betting applications.
