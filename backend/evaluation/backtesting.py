"""Backtesting framework for StatMusePicksV2

Provides a BacktestEngine that merges prediction outputs with actual
results and simulates a simple betting strategy. It follows the roadmap
guidance: only bet when EV > 0 and when confidence is above a threshold,
use a Kelly-derived stake fraction and cap per-bet exposure (default 2%
of bankroll).

Usage (CLI):
  python backend/evaluation/backtesting.py --predictions predictions.csv --actuals actuals.csv --outdir backtest_reports

Predictions CSV expected columns (case-insensitive):
  - game_date or date
  - player
  - line (numeric, optional)
  - predicted_value (numeric, optional)
  - over_probability or prob_over (numeric 0-1)
  - confidence (0-100 or 0-1)
  - expected_value (numeric)

Actuals CSV expected columns:
  - game_date or date
  - player
  - actual_value (numeric)

This implementation is intentionally lightweight and suitable for local
experimentation and CI smoke tests. For production, incorporate real odds
and vig adjustments when computing Kelly fractions.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import math
import os
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def remove_vig_from_market_odds(over_odds: float, under_odds: float) -> float:
    """Remove bookmaker vig given two-sided market decimal odds.

    Given market decimal odds for both sides (over_odds, under_odds), compute the
    fair (vig-removed) decimal odds for the 'over' side.

    Algorithm:
    - Convert to implied probabilities p_over = 1/over_odds, p_under = 1/under_odds
    - Normalize: fair_p_over = p_over / (p_over + p_under)
    - Return fair_decimal_odds = 1 / fair_p_over

    If inputs are invalid or missing, raises ValueError.
    """
    if over_odds is None or under_odds is None:
        raise ValueError("Both over_odds and under_odds are required to remove vig")
    try:
        p_over = 1.0 / float(over_odds)
        p_under = 1.0 / float(under_odds)
    except Exception:
        raise ValueError("Invalid odds provided")
    total = p_over + p_under
    if total <= 0:
        raise ValueError("Invalid implied probabilities from odds")
    fair_p_over = p_over / total
    if fair_p_over <= 0:
        raise ValueError("Computed non-positive fair probability")
    return 1.0 / fair_p_over


@dataclasses.dataclass
class BacktestResult:
    bets: pd.DataFrame
    initial_bankroll: float
    final_bankroll: float
    roi: float
    win_rate: float
    total_bets: int
    sharpe: Optional[float]
    max_drawdown: Optional[float] = None
    cagr: Optional[float] = None
    # Calibration metrics
    brier_score: Optional[float] = None
    calibration: Optional[pd.DataFrame] = None


class BacktestEngine:
    def __init__(self, predictions: pd.DataFrame):
        """Create engine with predictions DataFrame.

        Predictions are normalized internally; see module docstring for
        expected column names.
        """
        self.predictions = self._normalize_predictions(predictions.copy())

    @staticmethod
    def _normalize_predictions(df: pd.DataFrame) -> pd.DataFrame:
        df = df.rename(columns={c: c.lower() for c in df.columns})

        # Find a date column
        date_cols = [c for c in df.columns if c in ("game_date", "date", "game_date_utc")]
        if not date_cols:
            raise ValueError("Predictions DataFrame must contain a date/game_date column")
        df["game_date"] = pd.to_datetime(df[date_cols[0]])

        if "player" not in df.columns:
            raise ValueError("Predictions DataFrame must contain a 'player' column")

        # Normalise probability fields
        if "over_probability" not in df.columns:
            if "prob_over" in df.columns:
                df["over_probability"] = df["prob_over"]
            else:
                df["over_probability"] = 0.5

        # Normalize odds (decimal). Accept columns 'decimal_odds' or 'odds'
        if "decimal_odds" in df.columns:
            df["decimal_odds"] = pd.to_numeric(df["decimal_odds"], errors="coerce")
        elif "odds" in df.columns:
            df["decimal_odds"] = pd.to_numeric(df["odds"], errors="coerce")
        else:
            df["decimal_odds"] = 2.0

        # If the market provides both sides' odds (e.g. over and under), remove vig
        # and convert to fair decimal odds for the side we're modeling.
        if "decimal_odds_under" in df.columns:
            df["decimal_odds_under"] = pd.to_numeric(df["decimal_odds_under"], errors="coerce")
            # apply vig removal row-wise
            def _fair_over(row):
                over = row.get("decimal_odds")
                under = row.get("decimal_odds_under")
                try:
                    return remove_vig_from_market_odds(over, under)
                except Exception:
                    return over

            df["decimal_odds"] = df.apply(_fair_over, axis=1)

        # Normalise confidence to 0-1
        if "confidence" in df.columns:
            def _norm_conf(x):
                try:
                    xv = float(x)
                    return xv / 100.0 if xv > 1 else xv
                except Exception:
                    return 0.5

            df["confidence"] = df["confidence"].apply(_norm_conf)
        else:
            df["confidence"] = 0.5

        # Defaults
        if "expected_value" not in df.columns:
            df["expected_value"] = 0.0
        if "line" not in df.columns:
            df["line"] = np.nan

        for col in ("over_probability", "expected_value", "line", "confidence"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.sort_values("game_date").reset_index(drop=True)

    def load_actuals(self, actuals: pd.DataFrame) -> pd.DataFrame:
        df = actuals.rename(columns={c: c.lower() for c in actuals.columns})
        date_cols = [c for c in df.columns if c in ("game_date", "date")]
        if not date_cols:
            raise ValueError("Actuals DataFrame must contain a date/game_date column")
        df["game_date"] = pd.to_datetime(df[date_cols[0]])

        if "actual_value" not in df.columns:
            if "value" in df.columns:
                df["actual_value"] = df["value"]
            else:
                raise ValueError("Actuals DataFrame must contain 'actual_value' or 'value' column")

        df = df[["game_date", "player", "actual_value"]]
        df["actual_value"] = pd.to_numeric(df["actual_value"], errors="coerce")
        return df

    def _merge_with_actuals(self, actuals_df: pd.DataFrame) -> pd.DataFrame:
        preds = self.predictions.copy()
        actuals = actuals_df.copy()
        merged = pd.merge(preds, actuals, on=["player", "game_date"], how="left")
        return merged

    def run(
        self,
        actuals: pd.DataFrame,
        initial_bankroll: float = 1000.0,
        min_confidence: float = 0.6,
        require_ev_positive: bool = True,
        max_fraction_per_bet: float = 0.02,
        # Stake sizing options: 'kelly' (default), 'fixed_fraction', 'fixed_amount'
        stake_mode: str = "kelly",
        fixed_fraction: Optional[float] = None,
        fixed_amount: Optional[float] = None,
    ) -> BacktestResult:
        """Run the backtest simulation.

        Strategy (roadmap-aligned):
         - Only bet when EV > 0 (if `require_ev_positive`)
         - Only bet when `confidence` >= `min_confidence`
         - Kelly-derived fraction (generalized for decimal odds)
         - Cap stake fraction at `max_fraction_per_bet` (e.g., 0.02)
        """
        merged = self._merge_with_actuals(self.load_actuals(actuals))

        bankroll = float(initial_bankroll)
        initial = bankroll
        rows = []

        for _, r in merged.iterrows():
            if pd.isna(r.get("actual_value")):
                # skip unresolved outcomes
                continue

            raw_ev = r.get("expected_value", None)
            ev = float(raw_ev or 0.0)
            conf = float(r.get("confidence", 0.0) or 0.0)
            p = float(r.get("over_probability", 0.0) or 0.0)
            line = r.get("line")

            # Kelly-derived fraction generalized for decimal odds
            odds = float(r.get("decimal_odds", 2.0) or 2.0)
            b = odds - 1.0
            # If expected_value not provided (or zero), compute per-unit-stake EV from p and odds:
            # EV_per_unit = b*p - (1 - p)
            if raw_ev is None or (isinstance(raw_ev, (int, float)) and float(raw_ev) == 0.0):
                ev = b * p - (1.0 - p)

            # Apply EV and confidence filters after computing EV from odds when necessary
            if require_ev_positive and ev <= 0:
                continue
            if conf < min_confidence:
                continue

            # Determine stake according to selected stake sizing mode
            stake = 0.0
            if stake_mode == "kelly":
                if b > 0:
                    numerator = b * p - (1.0 - p)
                    kelly_f = max(0.0, numerator / b) if numerator > 0 else 0.0
                else:
                    kelly_f = max(0.0, 2.0 * p - 1.0)
                stake_fraction = min(kelly_f, max_fraction_per_bet)
                stake = bankroll * stake_fraction
            elif stake_mode == "fixed_fraction":
                # use user-supplied fixed_fraction or fall back to max_fraction_per_bet
                frac = float(fixed_fraction) if (fixed_fraction is not None) else float(max_fraction_per_bet)
                frac = min(frac, float(max_fraction_per_bet))
                stake = bankroll * frac
            elif stake_mode == "fixed_amount":
                if fixed_amount is None:
                    raise ValueError("fixed_amount must be provided when stake_mode='fixed_amount'")
                stake = float(fixed_amount)
                # never allow staking more than current bankroll
                stake = min(stake, bankroll)
            else:
                raise ValueError(f"Unknown stake_mode: {stake_mode}")

            if stake <= 0:
                continue

            actual = float(r.get("actual_value"))
            # Determine win/loss: compare actual to `line` if available,
            # otherwise to predicted_value as a fallback
            if pd.isna(line):
                line_check = float(r.get("predicted_value", 0.0) or 0.0)
                won = actual > line_check
            else:
                won = actual > float(line)

            # Payout for decimal odds: profit = stake * (odds - 1) on win, -stake on loss
            profit = stake * (odds - 1.0) if won else -stake
            bankroll += profit

            rows.append(
                {
                    "game_date": r["game_date"],
                    "player": r["player"],
                    "line": line,
                    "predicted_value": r.get("predicted_value"),
                    "over_probability": p,
                    "confidence": conf,
                    "expected_value": ev,
                    "decimal_odds": odds,
                    "stake": stake,
                    "won": bool(won),
                    "profit": profit,
                    "bankroll": bankroll,
                }
            )

        bets_df = pd.DataFrame(rows)

        total_bets = len(bets_df)
        wins = int(bets_df["won"].sum()) if total_bets > 0 else 0
        win_rate = float(wins / total_bets) if total_bets > 0 else 0.0
        final_bankroll = float(bankroll)
        roi = (final_bankroll - initial) / initial if initial > 0 else 0.0

        # Sharpe on per-bet returns relative to initial bankroll
        if total_bets > 1:
            returns = bets_df["profit"].astype(float) / float(initial)
            mean_r = returns.mean()
            std_r = returns.std(ddof=0)
            sharpe = (mean_r / std_r * math.sqrt(total_bets)) if std_r > 0 else None
        else:
            sharpe = None

        # Max drawdown: compute running peak of bankroll series and max drawdown
        if not bets_df.empty:
            series = bets_df["bankroll"].astype(float)
            running_max = series.cummax()
            drawdowns = (running_max - series) / running_max
            max_drawdown = float(drawdowns.max())

            # CAGR: compound annual growth rate between first and last bet dates
            first_date = pd.to_datetime(bets_df["game_date"].min())
            last_date = pd.to_datetime(bets_df["game_date"].max())
            years = (last_date - first_date).days / 365.25
            if years > 0 and initial > 0:
                cagr = float((final_bankroll / initial) ** (1.0 / years) - 1.0)
            else:
                cagr = None
        else:
            max_drawdown = None
            cagr = None

        # Calibration: compute Brier score and calibration buckets on all rows
        try:
            merged_eval = merged[~merged["actual_value"].isna()].copy()
            if not merged_eval.empty and "over_probability" in merged_eval.columns:
                # Derive binary outcome using line or predicted_value
                def _true_outcome(row):
                    if not pd.isna(row.get("line")):
                        return 1.0 if float(row.get("actual_value")) > float(row.get("line")) else 0.0
                    else:
                        pv = row.get("predicted_value")
                        check = float(pv) if (pv is not None and not pd.isna(pv)) else 0.0
                        return 1.0 if float(row.get("actual_value")) > check else 0.0

                merged_eval["_true_outcome"] = merged_eval.apply(_true_outcome, axis=1)
                merged_eval["_p"] = merged_eval["over_probability"].fillna(0.0).astype(float)
                # Brier score
                brier = float(((merged_eval["_p"] - merged_eval["_true_outcome"]) ** 2).mean())

                # Calibration buckets (10 bins)
                bins = np.linspace(0.0, 1.0, 11)
                merged_eval["_bin"] = pd.cut(merged_eval["_p"], bins=bins, include_lowest=True)
                calib = (
                    merged_eval.groupby("_bin")
                    .agg(
                        mean_pred=("_p", "mean"),
                        mean_obs=("_true_outcome", "mean"),
                        count=("_true_outcome", "count"),
                    )
                    .reset_index()
                )
            else:
                brier = None
                calib = None
        except Exception:
            brier = None
            calib = None

        return BacktestResult(
            bets=bets_df,
            initial_bankroll=initial,
            final_bankroll=final_bankroll,
            roi=roi,
            win_rate=win_rate,
            total_bets=total_bets,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            cagr=cagr,
            brier_score=brier,
            calibration=calib,
        )

    @staticmethod
    def save_report(result: BacktestResult, outdir: str, run_name: Optional[str] = None) -> str:
        os.makedirs(outdir, exist_ok=True)
        if run_name is None:
            # Use timezone-aware UTC timestamp to avoid deprecation warnings
            run_name = datetime.datetime.now(datetime.timezone.utc).strftime("backtest_%Y%m%dT%H%M%SZ")
        run_dir = os.path.join(outdir, run_name)
        os.makedirs(run_dir, exist_ok=True)

        result.bets.to_csv(os.path.join(run_dir, "bets.csv"), index=False)
        pd.DataFrame([
            {
                "initial_bankroll": result.initial_bankroll,
                "final_bankroll": result.final_bankroll,
                "roi": result.roi,
                "win_rate": result.win_rate,
                "total_bets": result.total_bets,
                "sharpe": result.sharpe,
                "max_drawdown": result.max_drawdown,
                "cagr": result.cagr,
                "brier_score": result.brier_score,
            }
        ]).to_csv(os.path.join(run_dir, "summary.csv"), index=False)

        # Charts are optional; don't fail if matplotlib missing
        try:
            import matplotlib.pyplot as plt

            if not result.bets.empty:
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.plot(result.bets["game_date"], result.bets["bankroll"], marker="o")
                ax.set_title("Bankroll Over Time")
                ax.set_xlabel("Game Date")
                ax.set_ylabel("Bankroll")
                fig.tight_layout()
                fig.savefig(os.path.join(run_dir, "bankroll.png"))
                plt.close(fig)

                fig2, ax2 = plt.subplots(figsize=(8, 4))
                ax2.plot(result.bets["game_date"], result.bets["profit"].cumsum())
                ax2.set_title("Cumulative Profit")
                ax2.set_xlabel("Game Date")
                ax2.set_ylabel("Cumulative Profit")
                fig2.tight_layout()
                fig2.savefig(os.path.join(run_dir, "cumulative_profit.png"))
                plt.close(fig2)
        except Exception:
            logger.debug("matplotlib not available or plotting failed; skipping charts")

        # Write calibration table if available
        try:
            if getattr(result, "calibration", None) is not None:
                calib_df = result.calibration
                # Ensure deterministic column order
                cols = [c for c in calib_df.columns if c in ("_bin", "mean_pred", "mean_obs", "count")]
                if cols:
                    calib_df = calib_df[cols]
                calib_df.to_csv(os.path.join(run_dir, "calibration.csv"), index=False)
        except Exception:
            logger.debug("Failed to write calibration CSV; skipping")

        return run_dir


def _read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run backtest from CSVs")
    parser.add_argument("--predictions", required=True, help="Predictions CSV path")
    parser.add_argument("--actuals", required=True, help="Actuals CSV path")
    parser.add_argument("--outdir", default="backend/evaluation/backtest_reports", help="Output directory")   
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--min-confidence", type=float, default=0.6)
    parser.add_argument("--max-fraction", type=float, default=0.02)
    args = parser.parse_args(argv)

    preds = _read_csv(args.predictions)
    actuals = _read_csv(args.actuals)

    engine = BacktestEngine(preds)
    result = engine.run(
        actuals,
        initial_bankroll=args.initial_bankroll,
        min_confidence=args.min_confidence,
        max_fraction_per_bet=args.max_fraction,
    )

    run_dir = BacktestEngine.save_report(result, args.outdir)
    print(f"Backtest complete. Report saved to: {run_dir}")


if __name__ == "__main__":
    main()
