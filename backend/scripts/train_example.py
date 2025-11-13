"""Very small helper script to exercise the training pipeline during development.

Usage (PowerShell):
  . .\.venv\Scripts\Activate.ps1; python backend/scripts/train_example.py
It will create a tiny synthetic dataset and save a model under `backend/models_store/`.
"""
from __future__ import annotations
import os
import sys
import pandas as pd
import numpy as np

# Ensure repo root is on sys.path so `backend` package imports work when
# this script is executed directly (script path becomes CWD for Python).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.training_pipeline import train_player_model, save_model
from backend.services.model_registry import ModelRegistry


def make_synthetic(n: int = 200):
    rng = np.random.default_rng(42)
    X1 = rng.normal(25, 5, size=n)
    X2 = rng.normal(3, 1, size=n)
    noise = rng.normal(0, 1, size=n)
    # target loosely correlated with X1
    target = X1 * 0.8 + X2 * 0.5 + noise

    df = pd.DataFrame({
        "recent_mean": X1,
        "recent_std": X2,
        "volatility": np.abs(noise),
        "target": target,
    })
    return df


def main():
    df = make_synthetic()
    model = train_player_model(df, target_col="target")
    out = os.path.abspath("backend/models_store/synthetic_player.pkl")
    # Save model artifact and persist metadata (version + notes) via ModelRegistry
    registry = ModelRegistry()
    # Example version: v0.1-synthetic
    registry.save_model("synthetic_player", model, version="v0.1-synthetic", notes="Synthetic training run")
    print("Wrote model to:", out)


if __name__ == "__main__":
    main()
