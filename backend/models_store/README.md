Model artifacts compatibility
=============================

This directory contains serialized model artifacts used by the ML prediction
service. Historically some artifacts were saved using project-specific ensemble
classes which require the original module path (e.g. `backend.models.ensemble_model`).

Compatibility notes
- The codebase provides a compatibility shim at `backend/models/ensemble_model.py`
  to allow unpickling legacy artifacts.
- For robust CI and runtime behavior, we prefer ``sklearn``-only artifacts.

Normalizing artifacts
- To convert legacy artifacts into sklearn-only artifacts, run:

```pwsh
$env:PYTHONPATH = "${PWD}"; python backend/scripts/normalize_models_to_sklearn.py
```

This script will back up original files with a `.orig` suffix and write
normalized sklearn-friendly `.pkl` files in place.

CI
- A GitHub Actions workflow `.github/workflows/model_registry_smoke.yml` runs the
  normalization script and the registry smoke-check as a CI smoke test.

If you need help converting or validating specific models, open an issue or
contact the ML team.
