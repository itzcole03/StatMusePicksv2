import numpy as np
import pytest
import pandas as pd
from backend.evaluation.backtesting import BacktestEngine


def test_backtest_simple():
    # create simple predictions DataFrame
    preds = pd.DataFrame([
        {"game_date": "2024-01-01", "player": "A", "line": 10, "predicted_value": 12, "over_probability": 0.7, "confidence": 0.8, "expected_value": 0.05},
        {"game_date": "2024-01-02", "player": "B", "line": 20, "predicted_value": 19, "over_probability": 0.4, "confidence": 0.9, "expected_value": -0.01},
    ])
    actuals = pd.DataFrame([
        {"game_date": "2024-01-01", "player": "A", "actual_value": 13},
        {"game_date": "2024-01-02", "player": "B", "actual_value": 18},
    ])

    engine = BacktestEngine(preds)
    result = engine.run(actuals, initial_bankroll=100.0, min_confidence=0.6, max_fraction_per_bet=0.02)

    # Only first bet should be placed (EV>0 and confidence>=0.6)
    assert result.total_bets == 1
    assert result.final_bankroll != result.initial_bankroll


def test_multiple_bets_and_odds(tmp_path):
    from backend.evaluation.backtesting import BacktestEngine

    preds = pd.DataFrame([
        {"game_date": "2025-01-01", "player": "A", "predicted_value": 10, "over_probability": 0.7, "confidence": 0.9, "decimal_odds": 2.5},
        {"game_date": "2025-01-02", "player": "B", "predicted_value": 8, "over_probability": 0.6, "confidence": 0.8, "decimal_odds": 1.8},
        {"game_date": "2025-01-03", "player": "C", "predicted_value": 7, "over_probability": 0.4, "confidence": 0.95, "decimal_odds": 2.0},
    ])

    actuals = pd.DataFrame([
        {"game_date": "2025-01-01", "player": "A", "actual_value": 11},
        {"game_date": "2025-01-02", "player": "B", "actual_value": 9},
        {"game_date": "2025-01-03", "player": "C", "actual_value": 6},
    ])

    engine = BacktestEngine(preds)
    result = engine.run(actuals, initial_bankroll=1000, min_confidence=0.5)

    # C should be skipped because its expected value (given p=0.4) is negative for typical odds
    assert result.total_bets == 2
    assert result.roi is not None
    assert result.win_rate is not None


def test_sharpe_and_roi_calculation(tmp_path):
    from backend.evaluation.backtesting import BacktestEngine

    preds = pd.DataFrame([
        {"game_date": "2025-02-01", "player": "X", "predicted_value": 12, "over_probability": 0.75, "confidence": 0.9, "decimal_odds": 2.0},
        {"game_date": "2025-02-02", "player": "Y", "predicted_value": 9, "over_probability": 0.65, "confidence": 0.85, "decimal_odds": 2.0},
    ])

    actuals = pd.DataFrame([
        {"game_date": "2025-02-01", "player": "X", "actual_value": 13},
        {"game_date": "2025-02-02", "player": "Y", "actual_value": 8},
    ])

    engine = BacktestEngine(preds)
    result = engine.run(actuals, initial_bankroll=1000, min_confidence=0.5)

    # With two bets, Sharpe should be computable (not None and finite)
    assert result.total_bets == 2
    assert isinstance(result.sharpe, float)
    assert not np.isnan(result.sharpe)


def test_deterministic_roi_and_sharpe(tmp_path):
    # Three bets, stake capped at 1% of current bankroll -> deterministic final bankroll
    preds = pd.DataFrame([
        {"game_date": "2025-04-01", "player": "P1", "predicted_value": 1, "over_probability": 0.9, "confidence": 0.99, "decimal_odds": 2.0},
        {"game_date": "2025-04-02", "player": "P2", "predicted_value": 1, "over_probability": 0.9, "confidence": 0.99, "decimal_odds": 2.0},
        {"game_date": "2025-04-03", "player": "P3", "predicted_value": 1, "over_probability": 0.9, "confidence": 0.99, "decimal_odds": 2.0},
    ])
    # outcomes: win, loss, win
    actuals = pd.DataFrame([
        {"game_date": "2025-04-01", "player": "P1", "actual_value": 2},
        {"game_date": "2025-04-02", "player": "P2", "actual_value": 0},
        {"game_date": "2025-04-03", "player": "P3", "actual_value": 2},
    ])

    engine = BacktestEngine(preds)
    initial = 1000.0
    cap = 0.01
    result = engine.run(actuals, initial_bankroll=initial, min_confidence=0.5, max_fraction_per_bet=cap, require_ev_positive=False)

    # Manually compute expected final bankroll with fixed 1% stake per bet (stake uses current bankroll)
    b1 = initial
    s1 = b1 * cap
    p1 = s1 * (2.0 - 1.0)  # win
    b2 = b1 + p1
    s2 = b2 * cap
    p2 = -s2  # loss
    b3 = b2 + p2
    s3 = b3 * cap
    p3 = s3 * (2.0 - 1.0)  # win
    expected_final = b3 + p3

    assert result.total_bets == 3
    assert result.final_bankroll == pytest.approx(expected_final, rel=1e-12)
    # ROI equals (final - initial) / initial
    assert result.roi == pytest.approx((expected_final - initial) / initial, rel=1e-12)


def test_remove_vig_helper():
    from backend.evaluation.backtesting import remove_vig_from_market_odds
    # Example: symmetrical market slightly favoured by vig; remove vig should return even money (2.0)
    over = 1.91
    under = 1.91
    fair = remove_vig_from_market_odds(over, under)
    assert pytest.approx(fair, rel=1e-6) == 2.0


def test_stake_cap_applied(tmp_path):
    from backend.evaluation.backtesting import BacktestEngine

    # Very high-confidence, very favorable odds -> would produce a large Kelly fraction
    preds = pd.DataFrame([
        {"game_date": "2025-03-01", "player": "Z", "predicted_value": 20, "over_probability": 0.99, "confidence": 0.99, "decimal_odds": 10.0},
    ])

    actuals = pd.DataFrame([
        {"game_date": "2025-03-01", "player": "Z", "actual_value": 21},
    ])

    engine = BacktestEngine(preds)
    max_frac = 0.02
    result = engine.run(actuals, initial_bankroll=10000, min_confidence=0.5, max_fraction_per_bet=max_frac)
    bets = result.bets
    assert len(bets) == 1
    # stake should not exceed the per-bet cap (fraction * initial_bankroll)
    assert bets.iloc[0]["stake"] <= 10000 * max_frac + 1e-6
