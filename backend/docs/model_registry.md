# Model Registry (local dev)
## Model Registry (local dev)

This document describes the lightweight per-version filesystem-backed Model Registry used for local development and CI smoke tests, and the adapter that allows legacy training code to continue saving joblib artifacts while also registering them in the per-version layout.

**Storage layout**

- Model versions are stored under: ``backend/models_store/<model_name>/versions/<version_id>/``
- Each `version_id` directory contains a ``metadata.json`` and a copy of the artifact file registered at creation time.

**Per-version registry (canonical for dev/CI)**

- Code: `backend/services/simple_model_registry.py`
- Primary APIs:
	- `ModelRegistry.register_model(name, artifact_src: Path|None, metadata: dict) -> ModelMetadata`
	- `ModelRegistry.list_models()`
	- `ModelRegistry.list_versions(name)`
	- `ModelRegistry.latest_model(name) -> Optional[ModelMetadata]`

Example usage:

```python
from pathlib import Path
from backend.services.simple_model_registry import ModelRegistry

reg = ModelRegistry()
meta = reg.register_model(
		"points-model",
		artifact_src=Path("./artifacts/points_v1.joblib"),
		metadata={"framework": "sklearn", "val_mae": 0.72},
)
print("registered:", meta.version_id, meta.artifact_path)

latest = reg.latest_model("points-model")
print(latest)
```

**Legacy `PlayerModelRegistry` adapter**

To preserve backwards compatibility with existing training scripts that call `PlayerModelRegistry.save_model()`, the legacy `backend/services/model_registry.py` now implements a best-effort adapter:

- `PlayerModelRegistry.save_model(player_name, model, ...)` still writes a legacy joblib artifact into `backend/models_store` and updates the legacy `index.json`.
- After a successful legacy save, the adapter will attempt to register the saved artifact with the per-version registry by calling `simple_model_registry.ModelRegistry.register_model()` using a compact metadata payload. Failures in registration are non-fatal (swallowed) so legacy behavior remains reliable.
- The adapter registers the artifact under the `safe` name (spaces replaced with underscores) to avoid filesystem issues.
- The per-version metadata includes a `schema_version` marker to support future migration.

This approach is intended as an incremental migration path: callers continue to use the legacy API while new tools and CI can read the per-version registry.

**Migration & best-practices**

- Backwards compatibility: keep `PlayerModelRegistry` API stable while making the per-version registry the canonical discovery surface in docs and new code.
- Atomic writes: per-version registry writes `metadata.json` atomically (write to temp and rename) to avoid partial state.
- Schema versioning: metadata includes `schema_version` (start at `1`) so readers can evolve safely.
- Deterministic-but-unique versions: the per-version registry computes a short sha1 prefix from name+metadata+timestamp to form `version_id`.

**Unit tests**

- There is a unit test verifying the per-version registry (`backend/tests/test_model_registry.py`).
- An adapter unit test was added to assert that calls to `PlayerModelRegistry.save_model()` invoke the per-version registration (`backend/tests/test_model_registry_adapter.py`).

**CI recommendations (smoke checks)**

- Add a lightweight CI job that runs:
	- `pytest backend/tests/test_model_registry.py -q`
	- `pytest backend/tests/test_model_registry_adapter.py -q`
	- Optionally run a tiny training smoke run on a small synthetic dataset to validate end-to-end `save_model()` behavior.

**Production migration (next phase)**

- This filesystem registry is intentionally simple. For production consider migrating to a managed registry solution such as MLflow, a database-backed index plus object storage (S3/GCS), or an artifacts service with RBAC and retention policies.
- Migration path: export per-version `metadata.json` and artifact paths, copy artifacts to object storage, and import into the target registry while preserving `version_id` and `created_at`.

If you need, I can create a migration script that enumerates `backend/models_store/*/versions/*/metadata.json` and bundles artifacts for upload to S3 or MLflow import.
