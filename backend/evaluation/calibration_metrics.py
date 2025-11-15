"""Clean calibration metrics implementation.

This module is used as the authoritative implementation to avoid issues
with earlier corrupted files in the package root.
"""
from typing import Tuple

import numpy as np


def brier_score(y_true, y_prob) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.shape != y_prob.shape:
        raise ValueError("y_true and y_prob must have the same shape")
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.shape != y_prob.shape:
        raise ValueError("y_true and y_prob must have the same shape")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    N = y_true.shape[0]
    if N == 0:
        return 0.0

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bin_edges, right=True)

    ece = 0.0
    for i in range(1, n_bins + 1):
        idx = bin_ids == i
        if not np.any(idx):
            continue
        avg_pred = float(np.mean(y_prob[idx]))
        acc = float(np.mean(y_true[idx]))
        prop = idx.sum() / N
        ece += prop * abs(avg_pred - acc)
    return float(ece)


def reliability_diagram(y_true, y_prob, n_bins: int = 10, ax=None) -> Tuple[object, object]:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError("matplotlib is required for plotting reliability diagrams") from exc

    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.shape != y_prob.shape:
        raise ValueError("y_true and y_prob must have the same shape")

    N = y_true.shape[0]
    if N == 0:
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        return fig, ax

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bin_edges, right=True)

    avg_pred_per_bin = []
    acc_per_bin = []
    for i in range(1, n_bins + 1):
        idx = bin_ids == i
        if not np.any(idx):
            avg_pred_per_bin.append(np.nan)
            acc_per_bin.append(np.nan)
            continue
        avg_pred_per_bin.append(float(np.mean(y_prob[idx])))
        acc_per_bin.append(float(np.mean(y_true[idx])))

    fig = None
    if ax is None:
        fig = plt.figure(figsize=(6, 6))
        ax = fig.add_subplot(1, 1, 1)

    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfectly calibrated")
    ax.plot(bin_centers, acc_per_bin, marker="o", label="Observed accuracy")
    ax.bar(bin_centers, np.nan_to_num(avg_pred_per_bin, nan=0.0) - np.nan_to_num(acc_per_bin, nan=0.0),
           width=1.0 / n_bins, alpha=0.3, align="center", label="Pred - Observed")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title("Reliability Diagram")
    ax.legend()

    return (fig if fig is not None else ax.get_figure()), ax


__all__ = ["brier_score", "expected_calibration_error", "reliability_diagram"]
