import math
from backend.services.feature_engineering import calculate_rolling_averages


def make_games(values):
    # most recent first
    return [{"statValue": v} for v in values]


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_calculate_rolling_averages_basic():
    vals = [30, 25, 20, 18, 22, 15, 10]
    recent = make_games(vals)
    out = calculate_rolling_averages(recent)

    # last3 avg = mean of [30,25,20]
    assert out["last_3_avg"] == (30 + 25 + 20) / 3

    # last5 avg
    assert out["last_5_avg"] == sum(vals[:5]) / 5

    # last10 avg (only 7 available) -> mean of all
    assert out["last_10_avg"] == sum(vals) / len(vals)

    # ema alpha 0.3: compute independently
    alpha = 0.3
    ema = vals[0]
    for v in vals[1:]:
        ema = alpha * v + (1 - alpha) * ema
    assert approx(out["exponential_moving_avg"], ema)

    # weighted moving averages: weights [3,2,1] for wma_3
    wma3 = (30*3 + 25*2 + 20*1) / (3 + 2 + 1)
    assert approx(out["wma_3"], wma3)

    # wma_5 weights [5,4,3,2,1]
    wma5 = sum([v * w for v, w in zip(vals[:5], [5,4,3,2,1])]) / sum([5,4,3,2,1])
    assert approx(out["wma_5"], wma5)

    # rolling std for last3 (population std)
    import numpy as np
    arr3 = np.array(vals[:3], dtype=float)
    expected_std3 = float(arr3.std(ddof=0))
    assert approx(out["last_3_std"], expected_std3)

    # min/max/median
    assert out["last_3_min"] == float(min(vals[:3]))
    assert out["last_3_max"] == float(max(vals[:3]))
    assert out["last_3_median"] == float(__import__("numpy").median(vals[:3]))

    # slope_10 computed over available values (7)
    x = list(range(len(vals)))
    import numpy as np
    slope, _ = np.polyfit(x, np.array(vals, dtype=float), 1)
    assert approx(out["slope_10"], float(slope))

    # momentum: current (30) - five_avg
    five_avg = sum(vals[:5]) / 5.0
    assert approx(out["momentum_vs_5_avg"], 30 - five_avg)


def test_empty_values():
    out = calculate_rolling_averages([])
    # All expected keys exist and are None
    keys = [
        "last_3_avg",
        "last_5_avg",
        "last_10_avg",
        "exponential_moving_avg",
        "wma_3",
        "wma_5",
        "last_3_std",
        "last_3_min",
        "last_3_max",
        "last_3_median",
        "slope_10",
        "momentum_vs_5_avg",
    ]
    for k in keys:
        assert out.get(k) is None
