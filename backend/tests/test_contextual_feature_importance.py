import numpy as np
import pandas as pd

from backend.services.feature_engineering import prune_contextual_features


def test_prune_contextual_features_keeps_signal_and_drops_noise():
    # Synthetic dataset: strong signal in 'trade_sentiment', noise in others
    rng = np.random.RandomState(42)
    n = 200
    trade = rng.normal(loc=0.5, scale=1.0, size=n)
    # other contextual noise features
    noise1 = rng.normal(size=n)
    noise2 = rng.normal(size=n)
    noise3 = rng.normal(size=n)

    # target correlated with trade_sentiment
    target = 2.0 * trade + rng.normal(scale=0.1, size=n)

    df = pd.DataFrame(
        {
            "trade_sentiment": trade,
            "is_playoff": rng.randint(0, 2, size=n),
            "is_national_tv": rng.randint(0, 2, size=n),
            "travel_distance_km": noise1,
            "opp_altitude_m": noise2,
            "is_contract_year": rng.randint(0, 2, size=n),
            "recent_awards_count": rng.randint(0, 3, size=n),
            "noise3": noise3,
            "target": target,
        }
    )

    pruned_df, kept = prune_contextual_features(df, target_col="target", threshold=0.02)

    # The strong signal 'trade_sentiment' should be kept
    assert "trade_sentiment" in kept
    # At least one noisy contextual numeric column should be dropped
    dropped_candidates = {"travel_distance_km", "opp_altitude_m", "noise3"}
    assert any(c not in pruned_df.columns for c in dropped_candidates)
