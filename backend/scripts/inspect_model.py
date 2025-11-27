"""Inspect a saved model file and attempt a test prediction to reproduce errors.

Usage: python backend/scripts/inspect_model.py path/to/model.pkl
"""

from __future__ import annotations

import os
import sys
import traceback

import joblib
import numpy as np
import pandas as pd

if len(sys.argv) < 2:
    print("Usage: inspect_model.py path/to/model.pkl")
    sys.exit(2)

path = sys.argv[1]
print("Loading model:", path)
if not os.path.exists(path):
    print("Model file not found")
    sys.exit(1)

try:
    m = joblib.load(path)
    print("Loaded OK; type:", type(m))
    if hasattr(m, "feature_names_in_"):
        print("model.feature_names_in_ length=", len(m.feature_names_in_))
        print(list(m.feature_names_in_))
    if hasattr(m, "estimators_"):
        print(
            "Model has estimators_ (ensemble). Listing first estimator types and feature names if present:"
        )
        for idx, est in enumerate(getattr(m, "estimators_", [])):
            print(" - estimator", idx, type(est))
            if hasattr(est, "feature_names_in_"):
                print("   estimator.feature_names_in_ len=", len(est.feature_names_in_))
    # build a dummy dataframe for prediction
    cols = None
    if hasattr(m, "feature_names_in_"):
        cols = list(m.feature_names_in_)
    elif hasattr(m, "estimators_") and len(getattr(m, "estimators_", [])) > 0:
        est = m.estimators_[0]
        if hasattr(est, "feature_names_in_"):
            cols = list(est.feature_names_in_)
    if cols is not None:
        print("Constructing dummy X with columns:", len(cols))
        X = pd.DataFrame(np.zeros((2, len(cols))), columns=cols)
    else:
        print("No feature names found; constructing numeric 2x5 array")
        X = pd.DataFrame(np.zeros((2, 5)), columns=[f"c{i}" for i in range(5)])
    try:
        p = m.predict(X)
        print("Predict succeeded; output shape:", np.asarray(p).shape)
    except Exception as e:
        print("Predict failed:")
        traceback.print_exc()
except Exception as e:
    print("Failed to load or inspect model:")
    traceback.print_exc()

print("Done")
