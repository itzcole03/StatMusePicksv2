import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
from backend.evaluation.calibration_metrics import brier_score, expected_calibration_error, reliability_diagram

# simple synthetic test
preds = np.array([0.1, 0.2, 0.8, 0.9, 0.6, 0.4])
labels = np.array([0, 0, 1, 1, 1, 0])
print('brier:', brier_score(preds, labels))
ece = expected_calibration_error(preds, labels, n_bins=3)
print('ece:', ece)
centers, avg_pred, acc, counts = reliability_diagram(preds, labels, n_bins=3)
print('centers:', centers)
print('avg_pred:', avg_pred)
print('acc:', acc)
print('counts:', counts)

# sanity asserts
assert abs(brier_score(preds, labels) - ((0.1-0)**2 + (0.2-0)**2 + (0.8-1)**2 + (0.9-1)**2 + (0.6-1)**2 + (0.4-0)**2)/6) < 1e-12
assert counts.sum() == len(preds)
print('ok')
