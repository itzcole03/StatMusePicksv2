"""Example usage for calibration metrics.

Run from the repo root (venv activated):

    python backend/evaluation/example_usage.py

The script prints Brier and ECE and saves a reliability diagram if matplotlib
is installed.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np

from backend.evaluation import calibration_metrics as cm


def main() -> int:
    rng = np.random.RandomState(0)
    n = 2000
    # construct miscalibrated predictions
    raw = rng.beta(2.0, 6.0, size=n)
    true_prob = 0.15 + 0.7 * raw
    true_prob = np.clip(true_prob, 0.0, 1.0)
    y = rng.binomial(1, true_prob, size=n)

    # holdout
    split = int(0.7 * n)
    raw_val, y_val = raw[split:], y[split:]

    brier = cm.brier_score(y_val, raw_val)
    ece = cm.expected_calibration_error(y_val, raw_val, n_bins=10)
    print(f"Brier score (raw): {brier:.6f}")
    print(f"ECE (raw): {ece:.6f}")

    out_dir = Path(".")
    try:
        fig, ax = cm.reliability_diagram(y_val, raw_val, n_bins=10)
        out_path = out_dir / "reliability_diagram_example.png"
        fig.savefig(out_path)
        print(f"Saved reliability diagram to: {out_path}")
    except RuntimeError:
        print("matplotlib not available; skipping plot")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
