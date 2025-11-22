"""Register smoke-trained models in the ModelRegistry.

This script scans a directory of model .pkl files (produced by
`scripts/smoke_train_players.py`), loads each model, and calls
`ModelRegistry.save_model()` to persist the artifact and insert metadata
into the `model_metadata` table (or local sqlite `dev.db` if
`DATABASE_URL` is not set).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json

from backend.services.model_registry import ModelRegistry
import joblib


def main(models_dir: str, version: str | None, notes: str | None):
    models_dir = Path(models_dir)
    if not models_dir.exists():
        raise SystemExit(f"Models dir not found: {models_dir}")

    registry = ModelRegistry()  # uses ./backend/models_store by default

    registered = []
    for p in sorted(models_dir.glob("*.pkl")):
        try:
            model = joblib.load(p)
            # derive player name from filename
            player = p.stem.replace("_", " ")
            registry.save_model(player, model, version=version, notes=notes)
            registered.append({"player": player, "path": str(p)})
            print(f"Registered model for {player}")
        except Exception as e:
            print(f"Failed to register {p}: {e}")

    out = models_dir.parent / "register_smoke_summary.json"
    with open(out, "w", encoding="utf8") as fh:
        json.dump(registered, fh, indent=2)
    print("Wrote summary to", out)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--models-dir", default="backend/models_store/smoke", help="Directory with .pkl models")
    p.add_argument("--version", default=None, help="Version string to attach to metadata")
    p.add_argument("--notes", default="smoke-trained models", help="Notes for metadata")
    args = p.parse_args()
    main(args.models_dir, args.version, args.notes)
