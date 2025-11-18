# Parquet CI: Export Datasets Workflow

This document describes the optional CI workflow `/.github/workflows/export_datasets.yml` which exercises the dataset export path and uploads artifacts.

Secrets
- `S3_BUCKET` - (optional) S3 bucket name to upload artifacts.
- `AWS_ACCESS_KEY_ID` - (optional) AWS access key ID with put/list permissions on `S3_BUCKET`.
- `AWS_SECRET_ACCESS_KEY` - (optional) AWS secret key.
- `AWS_REGION` - (optional) AWS region (defaults to `us-east-1`).

How it works
- The workflow installs optional parquet engines (`pyarrow` or `fastparquet`) if available.
- It runs `backend/scripts/ci_export_dataset.py` to create a small sample dataset and write to `artifacts/`.
- If `S3_BUCKET` and AWS credentials are set in Secrets, artifacts are synced to the bucket.
- Regardless, the workflow uploads `artifacts/` as a workflow artifact for download.

Manual trigger
- In GitHub UI -> Actions -> "Export Datasets (Parquet optional)" -> Run workflow.

Notes
- Parquet export is optional; if no parquet engine is available the export helper will fallback to gzipped CSV.
- For GCS upload, replace the S3 action with a GCS upload step and provide the corresponding secrets.
