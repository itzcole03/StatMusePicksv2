from __future__ import annotations

from typing import Tuple

import numpy as np


def brier_score(y_true: np.ndarray, p_pred: np.ndarray) -> float:
    """Compute the Brier score for binary outcomes.

    Args:
        y_true: array-like of shape (n,) with binary labels {0,1}
        p_pred: array-like of shape (n,) with predicted probabilities in [0,1]

    Returns:
        float Brier score (mean squared error between p_pred and y_true)
    """
    y = np.asarray(y_true).ravel()
    p = np.asarray(p_pred).ravel()
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(y_true: np.ndarray, p_pred: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE).

    Bins predictions into `n_bins` equal-width bins between 0 and 1. For each bin,
    compute the absolute difference between average predicted probability and
    empirical accuracy, then return a weighted average by bin size.
    """
    y = np.asarray(y_true).ravel()
    p = np.asarray(p_pred).ravel()
    assert y.shape == p.shape

    # Bin edges (include 1.0 in last bin)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idxs = np.digitize(p, bins, right=True) - 1
    ece = 0.0
    n = len(p)
    for i in range(n_bins):
        mask = bin_idxs == i
        if not mask.any():
            continue
        bin_size = mask.sum()
        avg_p = float(p[mask].mean())
        acc = float(y[mask].mean())
        ece += (bin_size / n) * abs(avg_p - acc)
    return float(ece)


def reliability_diagram_data(y_true: np.ndarray, p_pred: np.ndarray, n_bins: int = 10) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return data useful for plotting a reliability diagram.

    Returns:
        bin_centers, avg_pred_per_bin, acc_per_bin, counts_per_bin
    """
    y = np.asarray(y_true).ravel()
    p = np.asarray(p_pred).ravel()
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idxs = np.digitize(p, bins, right=True) - 1
    centers = (bins[:-1] + bins[1:]) / 2.0
    avg_preds = np.zeros(n_bins, dtype=float)
    accs = np.zeros(n_bins, dtype=float)
    counts = np.zeros(n_bins, dtype=int)
    for i in range(n_bins):
        mask = bin_idxs == i
        counts[i] = int(mask.sum())
        if counts[i] > 0:
            avg_preds[i] = float(p[mask].mean())
            accs[i] = float(y[mask].mean())
        else:
            avg_preds[i] = np.nan
            accs[i] = np.nan
    return centers, avg_preds, accs, counts


__all__ = ["brier_score", "expected_calibration_error", "reliability_diagram_data"]
