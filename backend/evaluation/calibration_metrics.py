"""Calibration metric utilities: Brier score, Expected Calibration Error (ECE),
and reliability-diagram data generator.

Lightweight, dependency-minimal implementations suitable for unit-testing and
CI. A small plotting helper is provided if `matplotlib` is available.
"""

from typing import Tuple

import numpy as np


def brier_score(y_true, y_prob) -> float:
    """Compute Brier score for binary outcomes.

    y_true: iterable of {0,1}
    y_prob: iterable of probabilities in [0,1]
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.shape != y_prob.shape:
        raise ValueError("y_true and y_prob must have the same shape")
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE).

    Bin predictions into `n_bins` equally-spaced buckets on [0,1]. ECE is the
    weighted (by bucket size) absolute difference between average predicted
    probability and observed frequency.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.shape != y_prob.shape:
        raise ValueError("y_true and y_prob must have the same shape")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bins) - 1
    n = len(y_true)
    ece = 0.0
    for i in range(n_bins):
        mask = bin_ids == i
        if not np.any(mask):
            continue
        avg_prob = float(np.mean(y_prob[mask]))
        avg_true = float(np.mean(y_true[mask]))
        ece += np.abs(avg_prob - avg_true) * (mask.sum() / n)
    return float(ece)


def reliability_diagram_data(
    y_true, y_prob, n_bins: int = 10
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return data for a reliability diagram.

    Returns (bin_centers, avg_pred, avg_true, counts) where each is a numpy array
    of length `n_bins`.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bins) - 1
    bin_centers = (bins[:-1] + bins[1:]) / 2.0
    avg_pred = np.zeros(n_bins, dtype=float)
    avg_true = np.zeros(n_bins, dtype=float)
    counts = np.zeros(n_bins, dtype=int)
    for i in range(n_bins):
        mask = bin_ids == i
        counts[i] = int(mask.sum())
        if counts[i] > 0:
            avg_pred[i] = float(np.mean(y_prob[mask]))
            avg_true[i] = float(np.mean(y_true[mask]))
        else:
            avg_pred[i] = 0.0
            avg_true[i] = 0.0

    return bin_centers, avg_pred, avg_true, counts


def plot_reliability_diagram(
    y_true, y_prob, n_bins: int = 10, ax=None, save_path: str = None
):
    """Optional convenience wrapper that plots a reliability diagram if
    `matplotlib` is available. Returns the matplotlib Axes if plotted, else None.
    """
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None

    bin_centers, avg_pred, avg_true, counts = reliability_diagram_data(
        y_true, y_prob, n_bins=n_bins
    )
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(bin_centers, avg_true, marker="o", label="Observed")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfectly Calibrated")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title("Reliability Diagram")
    ax.legend()
    if save_path:
        plt.savefig(save_path, bbox_inches="tight")
    return ax
