"""Resave model artifacts under `backend/models_store` using the
currently installed joblib/sklearn versions to reduce InconsistentVersionWarning
in tests.

This script attempts to load each `.pkl` file, then re-dumps it. It is
best-effort and will skip files that cannot be unpickled.
"""
import os
import warnings
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1] / 'models_store'

def resave_models():
    if not MODEL_DIR.exists():
        print(f"Model directory {MODEL_DIR} does not exist; nothing to do.")
        return

    files = list(MODEL_DIR.glob('*.pkl'))
    if not files:
        print("No .pkl model files found to resave.")
        return

    for f in files:
        print(f"Processing {f.name}...")
        try:
            # Suppress sklearn InconsistentVersionWarning during load
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                try:
                    import joblib
                except Exception:
                    print("joblib not available in this environment; skipping.")
                    continue

                model = joblib.load(f)

            # Re-dump using joblib to update metadata for current sklearn
            backup = f.with_suffix('.pkl.bak')
            try:
                f.rename(backup)
            except Exception:
                backup = None

            try:
                joblib.dump(model, f)
                print(f"Resaved {f.name} successfully.")
                if backup and backup.exists():
                    backup.unlink()
            except Exception as e:
                print(f"Failed to resave {f.name}: {e}")
                if backup and backup.exists():
                    # attempt to restore original
                    backup.rename(f)

        except Exception as e:
            print(f"Skipping {f.name}: failed to load ({e})")

if __name__ == '__main__':
    resave_models()
