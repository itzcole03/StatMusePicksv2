"""Backtesting scaffold: BacktestEngine for simulating betting strategies.

Includes: loading historical predictions + actuals, simple EV-based stake sizing (Kelly placeholder), and CSV report export.
"""
from typing import List, Dict, Optional
import csv
from pathlib import Path


class BacktestEngine:
    def __init__(self, starting_bankroll: float = 1000.0):
        self.starting_bankroll = float(starting_bankroll)
        self.bankroll = float(starting_bankroll)
        self.trades = []  # list of dicts with bet details

    def kelly_fraction(self, p: float, odds_decimal: float) -> float:
        """Compute Kelly fraction for binary bet with probability p and decimal odds."""
        # Kelly fraction = (bp - q) / b, where b = odds - 1, q = 1-p
        b = odds_decimal - 1.0
        q = 1.0 - p
        if b <= 0:
            return 0.0
        f = (b * p - q) / b
        return max(0.0, min(1.0, f))

    def stake(self, bankroll: float, fraction: float) -> float:
        return float(bankroll * max(0.0, min(1.0, fraction)))

    def run(self, predictions: List[Dict], odds_decimal: float = 1.909, kelly_cap: float = 0.1):
        """Run backtest over a list of prediction dicts.

        Each prediction dict should contain: 'predicted_prob' (float), 'actual_outcome' (0/1), and optionally 'predicted_value' and 'line'.
        """
        self.bankroll = float(self.starting_bankroll)
        self.trades = []
        for rec in predictions:
            p = float(rec.get('predicted_prob') or rec.get('over_probability') or 0.5)
            actual = int(rec.get('actual_outcome') or rec.get('actual') or 0)
            # Simple stake via Kelly fraction, capped
            f = self.kelly_fraction(p, odds_decimal)
            f = min(f, kelly_cap)
            stake_amt = self.stake(self.bankroll, f)
            if stake_amt <= 0:
                self.trades.append({'p': p, 'stake': 0.0, 'result': 0.0, 'bankroll': self.bankroll})
                continue

            # payout: if win, bankroll += stake * (odds_decimal - 1); if lose, bankroll -= stake
            if actual == 1:
                profit = stake_amt * (odds_decimal - 1.0)
            else:
                profit = -stake_amt

            self.bankroll += profit
            self.trades.append({'p': p, 'stake': stake_amt, 'result': profit, 'bankroll': self.bankroll})

        return {'final_bankroll': self.bankroll, 'trades': self.trades}

    def write_report(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['p', 'stake', 'result', 'bankroll'])
            w.writeheader()
            for t in self.trades:
                w.writerow(t)
"""Backtesting engine for betting strategies.

This module implements a simple BacktestEngine that simulates betting on
binary outcomes using model probabilities and market decimal odds.

Key strategy implementations:
- Fixed fraction staking when EV > 0
- Kelly fraction staking (bounded by max_fraction)

The engine returns a summary report and an optional CSV of bet-level results.
"""
from typing import List, Dict, Optional, Any
import math
import csv
import os
from dataclasses import dataclass

import numpy as np


@dataclass
class BetRecord:
    index: int
    pred_prob: float
    market_odds: float
    actual: int
    stake: float
    pnl: float


class BacktestEngine:
    def __init__(self, starting_bankroll: float = 1000.0):
        self.starting_bankroll = float(starting_bankroll)

    @staticmethod
    def implied_prob_from_decimal_odds(odds: float) -> float:
        # simple conversion without vig adjustment
        if odds <= 0:
            return 0.0
        return 1.0 / odds

    def simulate(self, records: List[Dict[str, Any]], strategy: str = 'kelly', fixed_fraction: float = 0.02, max_fraction: float = 0.2, save_csv: Optional[str] = None) -> Dict[str, Any]:
        """Simulate bets.

        Each record in `records` must include:
        - 'pred_prob': model probability of outcome
        - 'market_odds': decimal odds (e.g., 1.9)
        - 'actual': 0 or 1 outcome

        strategy: 'fixed' or 'kelly'
        """
        bankroll = self.starting_bankroll
        history: List[BetRecord] = []
        returns = []

        for i, r in enumerate(records):
            p = float(r.get('pred_prob'))
            odds = float(r.get('market_odds'))
            actual = int(r.get('actual'))

            b = odds - 1.0
            # expected value per unit stake
            ev = p * b - (1 - p)

            stake = 0.0
            if strategy == 'fixed':
                if ev > 0:
                    stake = bankroll * float(fixed_fraction)
            elif strategy == 'kelly':
                if b <= 0:
                    stake = 0.0
                else:
                    f = (p * (b + 1) - 1) / b  # fractional Kelly for decimal odds
                    # safe guard
                    if f <= 0:
                        stake = 0.0
                    else:
                        f = min(f, max_fraction)
                        stake = bankroll * f
            else:
                raise ValueError('unknown strategy')

            pnl = 0.0
            if stake > 0:
                if actual == 1:
                    pnl = stake * (odds - 1.0)
                else:
                    pnl = -stake

            bankroll += pnl
            history.append(BetRecord(i, p, odds, actual, stake, pnl))
            returns.append(pnl / (self.starting_bankroll if self.starting_bankroll > 0 else 1.0))

        # summary
        n_bets = sum(1 for b in history if b.stake > 0)
        net_profit = bankroll - self.starting_bankroll
        roi = net_profit / self.starting_bankroll
        win_rate = sum(1 for b in history if b.stake > 0 and b.pnl > 0) / (n_bets if n_bets else 1)

        # simple Sharpe: mean(PnL per bet) / std(PnL per bet) * sqrt(N)
        pnl_arr = np.array([b.pnl for b in history if b.stake > 0], dtype=float)
        if pnl_arr.size > 1 and pnl_arr.std(ddof=1) > 0:
            sharpe = float(pnl_arr.mean() / pnl_arr.std(ddof=1) * math.sqrt(len(pnl_arr)))
        else:
            sharpe = 0.0

        report = {
            'starting_bankroll': self.starting_bankroll,
            'ending_bankroll': bankroll,
            'net_profit': net_profit,
            'roi': roi,
            'n_bets': n_bets,
            'win_rate': win_rate,
            'sharpe': sharpe,
        }

        if save_csv:
            # write bet-level results
            try:
                os.makedirs(os.path.dirname(save_csv), exist_ok=True)
            except Exception:
                pass
            with open(save_csv, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['index', 'pred_prob', 'market_odds', 'actual', 'stake', 'pnl'])
                for b in history:
                    writer.writerow([b.index, b.pred_prob, b.market_odds, b.actual, b.stake, b.pnl])

        return {'report': report, 'history': history}


def write_report_json(report: dict, path: str) -> None:
    """Write the report dict to `path` as JSON. Creates parent dirs as needed."""
    import json

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, default=str)
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
    sharpe: float = 0.0


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

        # compute Sharpe ratio on per-bet PnL series (scaled by sqrt(N))
        pnl_list = []
        # Re-iterate to build per-bet pnl list (consistent with stakes used above)
        for _, row in df.iterrows():
            p = float(row.get(prob_col, 0.0))
            actual = int(row.get(actual_col, 0))
            odds = float(row.get(odds_col, 2.0) or 2.0)
            conf = float(row.get(confidence_col, 0.0)) if confidence_col else None

            if confidence_col and conf is not None and conf < min_confidence:
                continue

            ev = p * (odds - 1.0) - (1.0 - p) * 1.0
            if ev <= 0:
                continue

            if stake_mode == "flat":
                stake = float(flat_stake)
            else:
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

            if actual == 1:
                profit = stake * (odds - 1.0)
            else:
                profit = -stake

            pnl_list.append(float(profit))

        if len(pnl_list) > 1:
            pnl_arr = np.array(pnl_list, dtype=float)
            pnl_std = float(pnl_arr.std(ddof=1))
            if pnl_std > 0.0:
                sharpe = float(pnl_arr.mean() / pnl_std * math.sqrt(len(pnl_arr)))
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

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
            sharpe=sharpe,
        )
