# Research Findings: Sports Prediction AI Best Practices

## Key Finding 1: Model Calibration vs Accuracy (ScienceDirect 2024)

**Source:** Walsh & Joshi (2024) - "Machine learning for sports betting: Should model selection be based on accuracy or calibration?"

### Critical Insights:

- **Model calibration is MORE important than accuracy for sports betting**
- Using calibration for model selection: +34.69% ROI average vs -35.17% for accuracy-based selection
- Best case: +36.93% ROI (calibration) vs +5.56% (accuracy)
- Sports betting is a probabilistic decision-making problem where calibration matters most

### Key Highlights:

1. Sports bettors can leverage machine learning to earn a profit betting on the NBA
2. Model calibration is more important than accuracy for sports betting
3. Selecting models based on calibration leads to greater returns

### Implications for StatMusePicks:

- Current system focuses on accuracy metrics but should prioritize calibration
- Need to implement probability calibration techniques (Platt scaling, isotonic regression, temperature scaling)
- Model evaluation should measure calibration error (Brier score, ECE - Expected Calibration Error)

---

## Key Finding 2: Feature Engineering Critical

**Sources:** Multiple research papers emphasize feature engineering as crucial

### Important Features for NBA Prediction:

1. Recent performance trends (last 5-10 games)
2. Season averages
3. Opponent defensive metrics
4. Pace of play
5. Projected minutes
6. Home/away splits
7. Rest days between games
8. Player injury status
9. Team chemistry metrics
10. Historical matchup data

---

## Key Finding 3: Model Types

### Most Effective Models for Sports Betting:

1. **Random Forests** - Handle non-linear relationships well
2. **Gradient Boosting** (XGBoost, LightGBM) - High accuracy with proper tuning
3. **Neural Networks** - Complex pattern recognition
4. **Ensemble Methods** - Combine multiple models for better predictions

### Accuracy Benchmarks:

- Computer models: 70-85% accuracy for NBA player stat predictions
- Human experts: 65-70% accuracy
- Models edge out humans by 5-15%

---

## Key Finding 4: Data Requirements

### Training Data:

- Minimum: 1-2 seasons of historical data
- Optimal: 3-5+ seasons (650,000+ games for soccer models)
- Need player-level granular data, not just team-level

### Data Quality Issues:

- Missing data handling crucial
- Outlier detection and removal
- Feature normalization/standardization
- Time-series cross-validation (not random split)

---

## Key Finding 5: Common Pitfalls

1. **Overfitting** - Models memorize training data
2. **Look-ahead bias** - Using future information in training
3. **Ignoring bookmaker margins** - Need to beat the vig
4. **Poor calibration** - Overconfident predictions
5. **Insufficient feature engineering** - Raw stats not enough
6. **Not accounting for context** - Injuries, rest, motivation

---

## Next Steps for Analysis:

- Review NBA-specific prediction papers
- Examine feature engineering techniques in detail
- Research calibration methods
- Study ensemble approaches

---

## Key Finding 6: NBA Player Performance Prediction - Springer Study (2024)

**Source:** Papageorgiou, Sarlis & Tjortjis (2024) - "An innovative method for accurate NBA player performance forecasting"

### Methodology Highlights:

- **Individual player models**: 203 separate models (one per player) instead of single global model
- **Data span**: 2011-2012 to 2020-2021 seasons (10 years)
- **14 ML models tested**: Including Random Forest, AdaBoost, Bayesian Ridge, Elastic Net, Voting Meta-Model

### Performance Metrics:

- **MAPE (Mean Absolute Percentage Error)**: 28.90% - 29.50% on validation
- **MAE (Mean Absolute Error)**: 7.33 - 7.74 Fantasy Points
- **Real-world validation**: Top 18.4% ranking among 11,764 users in DFS tournament
- **Profitable line-ups**: Top 23.5% performance

### Key Success Factors:

#### 1. **Individual Player Modeling**

- Creating separate models for each player significantly improved accuracy
- Captures individual playing styles, tendencies, and patterns
- Better than one-size-fits-all global models

#### 2. **Feature Categories**

**Standard Features:**

- Points, rebounds, assists, steals, blocks
- Field goal %, 3-point %, free throw %
- Minutes played, turnovers, fouls

**Advanced Features:**

- Player Efficiency Rating (PER)
- Player Impact Estimate (PIE)
- Efficiency (EFF)
- Usage Rate
- True Shooting %
- Offensive/Defensive Ratings

**Result:** Standard features improved MAPE by 1.7-1.9% in evaluation, 0.2-2.1% in validation

#### 3. **Time Windows**

- Last 3 seasons (LTS) vs Last 10 seasons (TS) comparison
- More recent data (3 seasons) often performed better due to relevance
- Balance between data volume and recency critical

#### 4. **Best Performing Models**

1. **Voting Meta-Model** (ensemble of multiple models)
2. **Random Forest** - handles non-linearity well
3. **Bayesian Ridge** - good for uncertainty quantification
4. **AdaBoost** - boosting approach
5. **Elastic Net** - regularized linear model

#### 5. **Player Selection Criteria**

- Over 100 appearances from 2017-2018 to 2019-2020
- More than 30 appearances in 2020-2021 season
- Average participation time > 18 minutes
- **Excludes rookies and injured players** (insufficient data)

### Critical Insights for StatMusePicks:

1. **Per-player modeling is superior** to global models
2. **Advanced metrics matter** - PER, PIE, Usage Rate significantly improve predictions
3. **Ensemble methods** (Voting Meta-Model) outperform single models
4. **Feature engineering** with both standard and advanced stats is crucial
5. **Data recency vs volume tradeoff** - 3 seasons may be optimal for NBA

### Practical Application:

- Linear optimization used to select 8-player lineup
- Constraints: salary cap, player positions
- Objective: maximize total Fantasy Points
- Real-world profitability demonstrated
