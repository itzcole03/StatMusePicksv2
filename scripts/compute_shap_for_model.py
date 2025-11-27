"""Compute SHAP for the latest persisted model and save outputs.

Usage:
    python scripts/compute_shap_for_model.py [--model PATH] [--out-dir PATH]

If no model is provided, the script picks the most-recently modified file under
`backend/models_store/` with extension `.pkl` or `.pkl`/`.joblib`.

The script tries the following in order:
 - load the model with `joblib.load` and call `compute_shap(X)` if available
 - otherwise use `shap.TreeExplainer(model)` when `shap` is installed

The feature matrix `X` is loaded from `artifacts/*.csv` (first match) when present,
otherwise inferred by asking the model for `n_features_in_` or `num_features()` and
building a zero-filled DataFrame with that many columns.

Outputs (under `artifacts/shap/<modelname>/`):
 - `shap_values.npz` (numpy savez with arrays)
 - `expected_value.json` (scalar or list)
 - `sample_features.csv` (the X used)
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import logging
import os

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger("compute_shap")
logging.basicConfig(level=logging.INFO, format="%(message)s")

MODELS_DIR = os.path.join("backend", "models_store")
ARTIFACTS_DIR = "artifacts"


def find_latest_model(models_dir: str) -> str | None:
    patterns = [
        os.path.join(models_dir, "**", "*.pkl"),
        os.path.join(models_dir, "**", "*.joblib"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p, recursive=True))
    if not files:
        return None
    files = sorted(files, key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]


def find_sample_csv(artifacts_dir: str) -> str | None:
    pats = glob.glob(os.path.join(artifacts_dir, "*.csv"))
    return pats[0] if pats else None


def load_model(path: str):
    logger.info("Loading model from %s", path)
    return joblib.load(path)


def ensure_outdir(base: str, model_name: str) -> str:
    d = os.path.join(base, "shap", model_name)
    os.makedirs(d, exist_ok=True)
    return d


def infer_feature_matrix_from_model(model, n_samples: int = 50) -> pd.DataFrame:
    # Try common attributes
    n_features = None
    try:
        if hasattr(model, "n_features_in_"):
            n_features = int(getattr(model, "n_features_in_"))
    except Exception:
        n_features = None
    try:
        if (
            n_features is None
            and hasattr(model, "booster")
            and hasattr(model.booster, "num_features")
        ):
            n_features = int(model.booster.num_features())
    except Exception:
        pass
    try:
        if n_features is None and hasattr(model, "num_features"):
            n_features = int(model.num_features())
    except Exception:
        pass

    if n_features is None:
        n_features = 10
    cols = [f"f{i}" for i in range(n_features)]
    X = pd.DataFrame(np.zeros((n_samples, n_features)), columns=cols)
    return X


def preprocess_features(
    X: pd.DataFrame, max_onehot_cardinality: int = 30
) -> pd.DataFrame:
    """Prepare feature matrix for SHAP:
    - Keep numeric columns
    - One-hot encode categorical columns with cardinality <= max_onehot_cardinality
    - Drop extremely high-cardinality categoricals
    - Fill NaNs with 0
    """
    if not isinstance(X, pd.DataFrame):
        X = pd.DataFrame(X)

    # Numeric columns
    numeric = X.select_dtypes(include=[np.number]).copy()

    # Categorical/object columns
    cat = X.select_dtypes(exclude=[np.number]).copy()
    if not cat.empty:
        to_onehot = []
        to_drop = []
        for c in cat.columns:
            try:
                nunique = int(cat[c].nunique(dropna=True))
            except Exception:
                nunique = 0
            if nunique == 0:
                to_drop.append(c)
            elif nunique <= max_onehot_cardinality:
                to_onehot.append(c)
            else:
                to_drop.append(c)

        if to_onehot:
            try:
                oh = pd.get_dummies(
                    cat[to_onehot].astype(str), prefix=to_onehot, drop_first=False
                )
            except Exception:
                oh = pd.DataFrame()
        else:
            oh = pd.DataFrame()

        if to_drop:
            logger.info(
                "Dropping high-cardinality / empty categorical columns: %s", to_drop
            )

        Xp = pd.concat([numeric, oh], axis=1)
    else:
        Xp = numeric

    # Final cleanup
    Xp = Xp.fillna(0)
    # ensure numeric dtype
    for col in Xp.columns:
        if not np.issubdtype(Xp[col].dtype, np.number):
            Xp[col] = pd.to_numeric(Xp[col], errors="coerce").fillna(0)
    return Xp


def align_feature_count(X: pd.DataFrame, expected_n: int) -> pd.DataFrame:
    """Ensure X has exactly expected_n columns by truncating or padding with zero columns."""
    if expected_n is None:
        return X
    cur = X.shape[1]
    if cur == expected_n:
        return X
    if cur > expected_n:
        # truncate to first expected_n columns
        return X.iloc[:, :expected_n].copy()
    # pad with zero columns
    extra = expected_n - cur
    for i in range(extra):
        X[f"pad_{i}"] = 0.0
    return X


def compute_and_save_shap(model, X: pd.DataFrame, outdir: str, model_basename: str):
    try:
        import shap
    except Exception:
        logger.error(
            "`shap` library not installed. Install with `pip install shap` to enable SHAP computation."
        )
        return False

    # If model has compute_shap, prefer it
    expected = None
    shap_values = None
    try:
        if hasattr(model, "compute_shap"):
            logger.info("Model exposes `compute_shap`; using it.")
            expected, shap_values = model.compute_shap(X)
        else:
            logger.info("Using shap.TreeExplainer on the model instance.")
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X.values)
            expected = getattr(explainer, "expected_value", None)
    except Exception as e:
        logger.error("Exception while computing SHAP: %s", e)
        return False

    # Persist outputs
    npfile = os.path.join(outdir, "shap_values.npz")
    try:
        if isinstance(shap_values, list) or isinstance(shap_values, tuple):
            # save list of arrays
            savez_kwargs = {f"arr{i}": np.asarray(a) for i, a in enumerate(shap_values)}
        else:
            savez_kwargs = {"arr0": np.asarray(shap_values)}
        np.savez_compressed(npfile, **savez_kwargs)
    except Exception as e:
        logger.error("Failed to save shap npz: %s", e)
        return False

    jsonfile = os.path.join(outdir, "expected_value.json")
    try:
        with open(jsonfile, "w", encoding="utf-8") as fh:
            json.dump(
                expected.tolist() if hasattr(expected, "tolist") else expected, fh
            )
    except Exception:
        # best-effort
        try:
            with open(jsonfile, "w", encoding="utf-8") as fh:
                json.dump(str(expected), fh)
        except Exception:
            pass

    sample_csv = os.path.join(outdir, "sample_features.csv")
    try:
        X.to_csv(sample_csv, index=False)
    except Exception:
        pass

    logger.info("Saved SHAP outputs to %s", outdir)
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--model",
        help="Path to persisted model (joblib/pkl). If omitted, picks latest under backend/models_store/",
    )
    p.add_argument("--out-dir", help="Output artifacts base dir", default=ARTIFACTS_DIR)
    p.add_argument("--sample-csv", help="Optional CSV to use as feature matrix")
    args = p.parse_args()

    model_path = args.model
    if model_path is None:
        model_path = find_latest_model(MODELS_DIR)
    if model_path is None:
        logger.error("No model found under %s", MODELS_DIR)
        return

    model = load_model(model_path)
    sample_csv = args.sample_csv or find_sample_csv(args.out_dir)
    if sample_csv:
        try:
            X = pd.read_csv(sample_csv)
            logger.info("Loaded sample features from %s", sample_csv)
        except Exception as e:
            logger.warning(
                "Failed to read sample CSV %s: %s; falling back to inferred features",
                sample_csv,
                e,
            )
            X = infer_feature_matrix_from_model(model)
    else:
        X = infer_feature_matrix_from_model(model)

    # Preprocess to numeric features for SHAP
    Xp = preprocess_features(X)

    # Align to model's expected number of features if available
    expected = None
    try:
        expected = int(getattr(model, "n_features_in_", None))
    except Exception:
        expected = None
    if expected is not None:
        logger.info(
            "Model expects %s features; aligning processed sample (had %s)",
            expected,
            Xp.shape[1],
        )
        Xp = align_feature_count(Xp, expected)

    model_basename = os.path.splitext(os.path.basename(model_path))[0]
    outdir = ensure_outdir(
        args.out_dir,
        model_basename
        + "_"
        + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    # save the processed sample features used for SHAP
    try:
        Xp.to_csv(os.path.join(outdir, "sample_features_processed.csv"), index=False)
    except Exception:
        pass
    compute_and_save_shap(model, Xp, outdir, model_basename)


if __name__ == "__main__":
    main()
