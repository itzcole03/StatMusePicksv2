# CI Training Smoke Job — Secrets & Runner Notes

This document explains the minimal secrets, runner resources, timeouts and artifact locations required to run the `ci_train_smoke.yml` workflow safely.

Secrets (optional)
- `S3_BUCKET` — S3 bucket name to upload artifacts (optional).
- `AWS_ACCESS_KEY_ID` — AWS access key ID with put/list permissions on the S3 bucket.
- `AWS_SECRET_ACCESS_KEY` — AWS secret key.
- `AWS_REGION` — AWS region (defaults to `us-east-1`).

If you prefer GCS, replace the S3 sync step in the workflow with a GCS upload action and provide the corresponding service account key via a GitHub Secret (e.g. `GCP_SERVICE_ACCOUNT_KEY`).

Runner resources and timeouts
- The workflow uses `ubuntu-latest` by default. For the synthetic training job this is sufficient.
- Target run time: < 10 minutes for the synthetic example. Increase timeout if you enable larger datasets.
- If you add hyperparameter tuning (Optuna) or XGBoost heavy runs, consider a larger runner or self-hosted runner with more CPU/memory.
- Use job-level `timeout-minutes` in the workflow if you want to guard runaway runs.

Disk & artifacts
- Artifacts produced: `backend/models_store/` and any `artifacts/` directory created by CI scripts.
- Artifacts are uploaded via `actions/upload-artifact` and retained according to your repository settings.
- When uploading to S3/GCS, ensure the bucket lifecycle and permissions are configured for temporary artifacts to avoid storage bloat.

Caching dependencies
- Install time can be reduced by caching pip wheels or by reusing a layered Docker image with common dependencies.
- Consider adding `actions/cache` for `~/.cache/pip` keyed on `requirements.txt` to speed CI runs.

Local testing
- Run the synthetic example locally before enabling the workflow in CI:

```pwsh
# Activate virtualenv then run
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH='.'
python backend/scripts/train_example.py
```

Operational notes
- The CI workflow is intentionally conservative: it runs a small synthetic training example and uploads artifacts for inspection.
- If you enable training over real datasets in CI, add stricter resource/time limits and guardrails (max rows, sample mode, or dry-run flag).
- For production training CI, prefer separate scheduled training runs on dedicated runners or MLOps infra.

