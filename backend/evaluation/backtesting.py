from dataclasses import dataclass
from typing import Optional, Dict
import pandas as pd


@dataclass
class BacktestResult:
    start_bankroll: float
    final_bankroll: float
    total_bets: int
    wins: int
    losses: int
    win_rate: float
    total_profit: float
    roi: float
    avg_stake: float


class BacktestEngine:
    """Simple backtesting engine for prediction-based betting simulations.

    Expects a DataFrame with columns:
      - `pred_prob`: model's predicted probability of the event (0..1)
      - `actual`: 1 if event occurred, 0 otherwise
      - `odds`: decimal odds offered for the event (e.g., 2.0). If missing, defaults to 2.0
      - optional `confidence` column used to filter bets
    """

    def __init__(self, start_bankroll: float = 1000.0):
        self.start_bankroll = float(start_bankroll)

    def run(
        self,
        df: pd.DataFrame,
        prob_col: str = "pred_prob",
        actual_col: str = "actual",
        odds_col: str = "odds",
        confidence_col: Optional[str] = None,
        min_confidence: float = 0.0,
        stake_mode: str = "flat",  # or 'kelly'
        flat_stake: float = 10.0,
        kelly_cap: float = 0.25,
    ) -> BacktestResult:
        bankroll = float(self.start_bankroll)
        total_bets = 0
        wins = 0
        losses = 0
        total_staked = 0.0
        total_profit = 0.0

        for _, row in df.iterrows():
            p = float(row.get(prob_col, 0.0))
            actual = int(row.get(actual_col, 0))
            odds = float(row.get(odds_col, 2.0) or 2.0)
            conf = float(row.get(confidence_col, 0.0)) if confidence_col else None

            if confidence_col and conf is not None and conf < min_confidence:
                continue

            # Expected value for a unit stake: p*(odds-1) - (1-p)*1
            ev = p * (odds - 1.0) - (1.0 - p) * 1.0
            if ev <= 0:
                continue

            # Determine stake
            if stake_mode == "flat":
                stake = float(flat_stake)
            else:
                # Kelly fraction: f* = (bp - q) / b, where b = odds-1, q=1-p
                b = odds - 1.0
                q = 1.0 - p
                if b <= 0:
                    stake = float(flat_stake)
                else:
                    f = (b * p - q) / b
                    f = max(0.0, f)
                    f = min(f, kelly_cap)
                    stake = bankroll * f
            if stake <= 0 or stake > bankroll:
                continue

            # Place bet
            total_bets += 1
            total_staked += stake
            if actual == 1:
                profit = stake * (odds - 1.0)
                wins += 1
            else:
                profit = -stake
                losses += 1

            bankroll += profit
            total_profit += profit

        win_rate = (wins / total_bets) if total_bets > 0 else 0.0
        avg_stake = (total_staked / total_bets) if total_bets > 0 else 0.0
        roi = (bankroll - self.start_bankroll) / self.start_bankroll

        return BacktestResult(
            start_bankroll=self.start_bankroll,
            final_bankroll=bankroll,
            total_bets=total_bets,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_profit=total_profit,
            roi=roi,
            avg_stake=avg_stake,
        )
