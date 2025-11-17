import pandas as pd
import pytest
from backend.evaluation.backtesting import BacktestEngine


def test_fixed_amount_mode_and_metrics():
    # Three bets across a one-year span so CAGR is simple to calculate
    preds = pd.DataFrame([
        {"game_date": "2024-01-01", "player": "P1", "predicted_value": 1, "over_probability": 0.9, "confidence": 0.99, "decimal_odds": 2.0},
        {"game_date": "2024-07-01", "player": "P2", "predicted_value": 1, "over_probability": 0.9, "confidence": 0.99, "decimal_odds": 2.0},
        {"game_date": "2025-01-01", "player": "P3", "predicted_value": 1, "over_probability": 0.9, "confidence": 0.99, "decimal_odds": 2.0},
    ])
    # outcomes: win, loss, win
    actuals = pd.DataFrame([
        {"game_date": "2024-01-01", "player": "P1", "actual_value": 2},
        {"game_date": "2024-07-01", "player": "P2", "actual_value": 0},
        {"game_date": "2025-01-01", "player": "P3", "actual_value": 2},
    ])

    engine = BacktestEngine(preds)
    initial = 1000.0
    result = engine.run(actuals, initial_bankroll=initial, min_confidence=0.5, stake_mode="fixed_amount", fixed_amount=50.0, require_ev_positive=False)

    # final bankroll manual calculation: +50, -50, +50 => 1050
    assert result.total_bets == 3
    assert result.final_bankroll == pytest.approx(1050.0, rel=1e-12)

    # CAGR over roughly one year should be about 5% (allow small calendar tolerances)
    assert result.cagr == pytest.approx(0.05, rel=3e-3)

    # max_drawdown: running bankroll is [1000,1050,1000,1050], drawdown peak->trough is 50/1050
    assert result.max_drawdown == pytest.approx((1050.0 - 1000.0) / 1050.0, rel=1e-9)


def test_fixed_fraction_respects_cap():
    preds = pd.DataFrame([
        {"game_date": "2025-03-01", "player": "Z", "predicted_value": 20, "over_probability": 0.99, "confidence": 0.99, "decimal_odds": 10.0},
    ])
    actuals = pd.DataFrame([
        {"game_date": "2025-03-01", "player": "Z", "actual_value": 21},
    ])
    engine = BacktestEngine(preds)
    max_frac = 0.02
    # Request an excessive fixed_fraction of 50% but engine should cap at max_fraction_per_bet
    result = engine.run(actuals, initial_bankroll=10000, min_confidence=0.5, stake_mode="fixed_fraction", fixed_fraction=0.5, max_fraction_per_bet=max_frac, require_ev_positive=False)
    bets = result.bets
    assert len(bets) == 1
    assert bets.iloc[0]["stake"] <= 10000 * max_frac * 1.000001