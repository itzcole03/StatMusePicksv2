import numpy as np
from backend.evaluation import calibration_metrics as cm


def test_brier_score_perfect_and_half():
    y_true = [0, 1]
    y_prob_perfect = [0.0, 1.0]
    assert cm.brier_score(y_true, y_prob_perfect) == 0.0

    y_prob_half = [0.5, 0.5]
    # (0.5^2 + 0.5^2) / 2 = 0.25
    assert abs(cm.brier_score(y_true, y_prob_half) - 0.25) < 1e-8


def test_ece_simple_two_bins():
    # four predictions split into two bins: [0.1,0.2] and [0.8,0.9]
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])
    y_true = np.array([0, 0, 1, 1])
    # With 2 bins, avg probs are 0.15 and 0.85; observed freqs are 0 and 1.
    # ECE = |0.15-0|*(2/4) + |0.85-1|*(2/4) = 0.15
    ece = cm.expected_calibration_error(y_true, y_prob, n_bins=2)
    assert abs(ece - 0.15) < 1e-8


def test_reliability_diagram_data_counts_and_values():
    y_prob = np.array([0.05, 0.15, 0.45, 0.55, 0.95])
    y_true = np.array([0, 0, 0, 1, 1])
    centers, avg_pred, avg_true, counts = cm.reliability_diagram_data(y_true, y_prob, n_bins=5)
    assert len(centers) == 5
    assert counts.sum() == len(y_true)
    # check that bins with values have avg_pred > 0
    assert avg_pred[counts > 0].min() > 0
