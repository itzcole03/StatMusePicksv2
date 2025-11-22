import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from backend.evaluation.backtesting import BacktestEngine

preds = [
    {'predicted_prob': 0.6, 'actual_outcome': 1},
    {'predicted_prob': 0.55, 'actual_outcome': 0},
    {'predicted_prob': 0.7, 'actual_outcome': 1},
    {'predicted_prob': 0.4, 'actual_outcome': 0},
]

engine = BacktestEngine(start_bankroll=1000.0)
import pandas as pd
df = pd.DataFrame([
    {'pred_prob': 0.6, 'actual': 1, 'odds': 1.909},
    {'pred_prob': 0.55, 'actual': 0, 'odds': 1.909},
    {'pred_prob': 0.7, 'actual': 1, 'odds': 1.909},
    {'pred_prob': 0.4, 'actual': 0, 'odds': 1.909},
])
res = engine.run(df, prob_col='pred_prob', actual_col='actual', odds_col='odds', stake_mode='kelly', flat_stake=10.0)
print('final bankroll', res.final_bankroll, 'roi', res.roi)
