from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Dict, Optional, List, Any


@dataclass
class ModelMetadata:
    name: str
    version_id: str
    created_at: str
    artifact_path: str
    metadata: Dict[str, Any]


class ModelRegistry:
    """A lightweight filesystem-backed model registry for local dev/CI.

    Stores model versions under a base directory with structure:
      <base_path>/<model_name>/versions/<version_id>/metadata.json
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = Path(base_path or Path(__file__).resolve().parents[2] / "models_store")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _model_dir(self, name: str) -> Path:
        return self.base_path / name / "versions"

    def _compute_version_id(self, name: str, metadata: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({"name": name, "metadata": metadata, "created_at": now}, sort_keys=True)
        return sha1(payload.encode("utf-8")).hexdigest()[:12]

    def register_model(self, name: str, artifact_src: Optional[Path], metadata: Optional[Dict[str, Any]] = None) -> ModelMetadata:
        metadata = metadata or {}
        version_id = self._compute_version_id(name, metadata)
        version_dir = self._model_dir(name) / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        artifact_dest = ""
        if artifact_src:
            artifact_src = Path(artifact_src)
            if not artifact_src.exists():
                raise FileNotFoundError(f"artifact not found: {artifact_src}")
            artifact_dest = str(version_dir / artifact_src.name)
            shutil.copy2(str(artifact_src), artifact_dest)

        created_at = datetime.now(timezone.utc).isoformat()

        meta = ModelMetadata(name=name, version_id=version_id, created_at=created_at, artifact_path=artifact_dest, metadata=metadata)
        with open(version_dir / "metadata.json", "w", encoding="utf-8") as fh:
            json.dump(asdict(meta), fh, indent=2, sort_keys=True)
        return meta

    def list_models(self) -> List[str]:
        return [p.name for p in self.base_path.iterdir() if p.is_dir()]

    def list_versions(self, name: str) -> List[str]:
        dirp = self._model_dir(name)
        if not dirp.exists():
            return []
        return [p.name for p in dirp.iterdir() if p.is_dir()]

    def latest_model(self, name: str) -> Optional[ModelMetadata]:
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
                    found = ModelMetadata(**data)
        return found


__all__ = ["ModelRegistry", "ModelMetadata"]
