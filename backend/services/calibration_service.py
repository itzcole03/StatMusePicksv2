from __future__ import annotations

import json
import joblib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass
class CalibratorMetadata:
    name: str
    version_id: str
    created_at: str
    calibrator_path: str
    metadata: Dict[str, Any]


class Calibrator:
    """Wrapper around sklearn's IsotonicRegression to provide a simple API."""

    def __init__(self, ir: Optional[IsotonicRegression] = None):
        self.ir = ir or IsotonicRegression(out_of_bounds="clip")

    def fit(self, raw_preds: np.ndarray, y_true: np.ndarray) -> "Calibrator":
        # Expect raw_preds shape (n,) and y_true in {0,1}
        self.ir.fit(raw_preds, y_true)
        return self

    def predict(self, raw_preds: np.ndarray) -> np.ndarray:
        preds = self.ir.predict(raw_preds)
        # Clip to [0,1]
        return np.clip(preds, 0.0, 1.0)


class CalibratorRegistry:
    """Filesystem-backed registry for calibrators (dev/CI friendly).

    Structure:
      <base_path>/<model_name>/versions/<version_id>/calibrator.joblib
      <base_path>/<model_name>/versions/<version_id>/metadata.json
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = Path(base_path or Path(__file__).resolve().parents[2] / "calibrators_store")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _model_dir(self, name: str) -> Path:
        return self.base_path / name / "versions"

    def _compute_version_id(self, name: str, metadata: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({"name": name, "metadata": metadata, "created_at": now}, sort_keys=True)
        return sha1(payload.encode("utf-8")).hexdigest()[:12]

    def register_calibrator(self, name: str, calibrator: Calibrator, metadata: Optional[Dict[str, Any]] = None) -> CalibratorMetadata:
        metadata = metadata or {}
        version_id = self._compute_version_id(name, metadata)
        version_dir = self._model_dir(name) / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        calibrator_path = str(version_dir / "calibrator.joblib")
        joblib.dump(calibrator, calibrator_path)

        created_at = datetime.now(timezone.utc).isoformat()
        meta = CalibratorMetadata(name=name, version_id=version_id, created_at=created_at, calibrator_path=calibrator_path, metadata=metadata)
        with open(version_dir / "metadata.json", "w", encoding="utf-8") as fh:
            json.dump(asdict(meta), fh, indent=2, sort_keys=True)
        return meta

    def list_models(self):
        return [p.name for p in self.base_path.iterdir() if p.is_dir()]

    def list_versions(self, name: str):
        dirp = self._model_dir(name)
        if not dirp.exists():
            return []
        return [p.name for p in dirp.iterdir() if p.is_dir()]

    def latest_calibrator(self, name: str) -> Optional[CalibratorMetadata]:
        versions = self.list_versions(name)
        if not versions:
            return None
        found = None
        for v in versions:
            mpath = self._model_dir(name) / v / "metadata.json"
            if not mpath.exists():
                continue
            with open(mpath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if found is None or data.get("created_at", "") > found.created_at:
                    found = CalibratorMetadata(**data)
        return found

    def load_calibrator(self, name: str, version_id: Optional[str] = None) -> Optional[Calibrator]:
        if version_id is None:
            meta = self.latest_calibrator(name)
            if meta is None:
                return None
            path = Path(meta.calibrator_path)
        else:
            path = self._model_dir(name) / version_id / "calibrator.joblib"

        if not path.exists():
            return None
        return joblib.load(str(path))


def fit_isotonic_and_register(name: str, raw_preds: np.ndarray, y_true: np.ndarray, registry: Optional[CalibratorRegistry] = None, metadata: Optional[Dict[str, Any]] = None) -> CalibratorMetadata:
    """Fit an isotonic calibrator from raw predictions -> binary outcomes and register it."""
    registry = registry or CalibratorRegistry()
    raw_preds = np.asarray(raw_preds).ravel()
    y_true = np.asarray(y_true).ravel()
    calib = Calibrator()
    calib.fit(raw_preds, y_true)
    return registry.register_calibrator(name, calib, metadata=metadata)


def apply_calibrator(name: str, raw_preds: np.ndarray, registry: Optional[CalibratorRegistry] = None, version_id: Optional[str] = None) -> Optional[np.ndarray]:
    registry = registry or CalibratorRegistry()
    calib = registry.load_calibrator(name, version_id=version_id)
    if calib is None:
        return None
    return calib.predict(np.asarray(raw_preds).ravel())


def brier_score(y_true: np.ndarray, p_pred: np.ndarray) -> float:
    y = np.asarray(y_true).ravel()
    p = np.asarray(p_pred).ravel()
    return float(np.mean((p - y) ** 2))


__all__ = [
    "Calibrator",
    "CalibratorRegistry",
    "fit_isotonic_and_register",
    "apply_calibrator",
    "brier_score",
    "CalibratorMetadata",
]
