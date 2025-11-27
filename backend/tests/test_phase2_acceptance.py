import os
import subprocess
from pathlib import Path

import pandas as pd


def ensure_metrics_generated():
    csv = Path("backend/tests/fixtures/calib/calibration_metrics.csv")
    manifest = Path("backend/tests/fixtures/calib/manifest.json")
    models_dir = Path("backend/tests/fixtures/calib/models")
    if csv.exists():
        return csv
    # try to (re)run the compute script using the fixture manifest if present
    if manifest.exists() and models_dir.exists():
        cmd = [
            "python",
            "scripts/compute_calibration_metrics.py",
            "--manifest",
            str(manifest),
            "--models-dir",
            str(models_dir),
            "--csv-out",
            str(csv),
        ]
        subprocess.check_call(cmd)
        return csv
    raise RuntimeError("Calibration metrics CSV not found and fixtures not present")


def test_phase2_acceptance_basic():
    """Basic acceptance checks for Phase 2: artifacts exist and columns present.

    If `PHASE2_STRICT=1` is set in the environment, also enforce an optional
    Brier score threshold (default 0.20) across players' calibrated metrics.
    """
    csv = ensure_metrics_generated()
    df = pd.read_csv(csv)
    # basic sanity
    assert not df.empty, "Calibration metrics CSV is empty"
    required = {"player", "brier_after", "mse_after"}
    assert required.issubset(
        set(df.columns)
    ), f"Missing required cols: {required - set(df.columns)}"

    # optional strict threshold (CI won't enable by default)
    if os.environ.get("PHASE2_STRICT") == "1":
        threshold = float(os.environ.get("PHASE2_BRIER_THRESHOLD", "0.20"))
        # ignore nulls
        vals = df["brier_after"].dropna().astype(float)
        assert len(vals) > 0, "No calibrated brier values to evaluate"
        mean_brier = float(vals.mean())
        assert (
            mean_brier <= threshold
        ), f"Mean Brier {mean_brier:.4f} > threshold {threshold}"
