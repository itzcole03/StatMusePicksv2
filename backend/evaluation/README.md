# Evaluation / Calibration Metrics

This folder provides lightweight calibration metrics used by the backend:

- `brier_score(y_true, y_prob)` — mean squared error between predicted probability and outcome.
- `expected_calibration_error(y_true, y_prob, n_bins=10)` — ECE using equal-width bins.
- `reliability_diagram(y_true, y_prob, n_bins=10, ax=None)` — plot a reliability diagram (requires `matplotlib`).

Usage examples:

```python
from backend.evaluation import calibration_metrics as cm
import numpy as np

n = 1000
rng = np.random.RandomState(0)
true_prob = rng.uniform(0.1, 0.9, size=n)
y = rng.binomial(1, true_prob)
pred = true_prob * 0.9 + 0.05  # slightly biased

print('Brier:', cm.brier_score(y, pred))
print('ECE:', cm.expected_calibration_error(y, pred, n_bins=10))

# To plot (optional):
try:
    fig, ax = cm.reliability_diagram(y, pred, n_bins=10)
    fig.savefig('reliability_diagram.png')
    print('Saved reliability_diagram.png')
except RuntimeError:
    print('matplotlib not available; skipping plot')
```

The `example_usage.py` script in the same folder provides a runnable demonstration.
