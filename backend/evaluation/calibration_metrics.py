from __future__ import annotations
import numpy as np
from typing import Tuple


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Compute Brier score for probabilistic predictions.

    y_true: binary 0/1 array (or 0/1-like)
    y_prob: predicted probabilities in [0,1]
    """
    y_true = np.asarray(y_true).ravel()
    y_prob = np.asarray(y_prob).ravel()
    if y_true.shape != y_prob.shape:
        raise ValueError("Shapes of y_true and y_prob must match")
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE).

    Bin predictions into `n_bins` uniform bins and compute weighted absolute difference
    between average predicted probability and empirical accuracy.
    """
    y_true = np.asarray(y_true).ravel()
    y_prob = np.asarray(y_prob).ravel()
    if y_true.shape != y_prob.shape:
        raise ValueError("Shapes of y_true and y_prob must match")

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bins) - 1
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        mask = bin_ids == i
        if not np.any(mask):
            continue
        p_avg = float(np.mean(y_prob[mask]))
        acc = float(np.mean(y_true[mask]))
        ece += (np.sum(mask) / n) * abs(p_avg - acc)
    return float(ece)


def calibration_summary(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> Tuple[float, float]:
    """Return (brier, ece)."""
    return brier_score(y_true, y_prob), expected_calibration_error(y_true, y_prob, n_bins=n_bins)
