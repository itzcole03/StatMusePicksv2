"""A tiny training stub that fits a trivial model and registers it.

This script is intentionally lightweight: it trains a small linear model
if scikit-learn is available, otherwise it saves a simple dict as a
placeholder model. It demonstrates how to use `PlayerModelRegistry`.
"""
from __future__ import annotations

import sys
from pathlib import Path

from backend.services.model_registry import PlayerModelRegistry


def train_dummy():
    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression

        X = np.arange(20).reshape(-1, 1)
        y = (2 * X.squeeze()) + 1
        m = LinearRegression()
        m.fit(X, y)
        return m, {"model_type": "LinearRegression", "metrics": {"mae": 0.0}}
    except Exception:
        # fallback: simple serializable dict
        model = {"coef": [2.0], "intercept": 1.0}
        return model, {"model_type": "dict_stub", "metrics": {}}


def main():
    out_dir = Path("backend/models_store")
    out_dir.mkdir(parents=True, exist_ok=True)
    reg = PlayerModelRegistry(str(out_dir))
    player = "Stub Player"
    model, metadata = train_dummy()
    version = reg.save_model(player, model, metadata=metadata)
    print("Saved model for", player, "version", version)


if __name__ == "__main__":
    main()
