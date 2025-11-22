import pandas as pd
from backend.evaluation.backtesting import BacktestEngine


def test_backtest_engine_run():
    # create DataFrame with pred_prob, actual, odds
    n = 100
    df = pd.DataFrame({
        'pred_prob': [0.6] * n,
        'actual': [1 if i % 2 == 0 else 0 for i in range(n)],
        'odds': [2.0] * n,
    })

    engine = BacktestEngine(start_bankroll=1000.0)
    res = engine.run(df, prob_col='pred_prob', actual_col='actual', odds_col='odds', stake_mode='flat', flat_stake=5.0)

    assert res.total_bets >= 0
    assert res.final_bankroll is not None
