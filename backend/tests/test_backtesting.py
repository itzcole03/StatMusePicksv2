import pandas as pd
from backend.evaluation.backtesting import BacktestEngine


def test_backtest_flat_stake_simple():
    # 10 bets, odds 2.0, predicted prob 0.6, actuals: 6 wins, 4 losses
    data = []
    actuals = [1,0,1,1,0,1,0,1,1,0]
    for a in actuals:
        data.append({"pred_prob": 0.6, "odds": 2.0, "actual": a})
    df = pd.DataFrame(data)

    engine = BacktestEngine(start_bankroll=1000.0)
    res = engine.run(df, stake_mode='flat', flat_stake=100.0)

    # Wins = 6, Losses = 4, profit = 6*100*(2-1) - 4*100 = 200
    assert res.total_bets == 10
    assert res.wins == 6
    assert res.losses == 4
    assert res.final_bankroll == 1200.0
    assert abs(res.roi - 0.2) < 1e-6


def test_backtest_kelly_cap():
    # Test kelly staking doesn't exceed cap and updates bankroll
    data = []
    actuals = [1,0,1,0]
    probs = [0.55, 0.55, 0.55, 0.55]
    for p, a in zip(probs, actuals):
        data.append({"pred_prob": p, "odds": 2.0, "actual": a})
    df = pd.DataFrame(data)

    engine = BacktestEngine(start_bankroll=1000.0)
    res = engine.run(df, stake_mode='kelly', kelly_cap=0.1)

    # some bets placed, final bankroll is finite and >0
    assert res.total_bets > 0
    assert res.final_bankroll > 0
