Migration Rollout & Safety Guide
================================

This document describes best-practice steps to safely roll out database migrations that affect `model_metadata` and related ML artifact metadata.

1. Backup database
------------------
- Take a consistent backup of your production DB (pg_dump for Postgres).
- If using snapshots, create a point-in-time snapshot before making schema changes.

2. Dry-run duplicate detection
------------------------------
- Run the provided dedupe utility in dry-run mode to detect duplicate `(name, version)` rows that would block unique constraints.

```bash
python backend/scripts/dedupe_model_metadata.py --dry-run
```

- Review the generated CSV report and decide whether to apply deletions.

3. Apply safe dedupe with backup
--------------------------------
- If you decide to remove duplicates, run with `--apply --backup` which will write a CSV backup before deleting rows.

```bash
python backend/scripts/dedupe_model_metadata.py --apply --backup
```

4. Run Alembic migration smoke test
-----------------------------------
- On a CI job or a staging DB, run Alembic upgrade in SQL-generation mode to surface errors:

```bash
pushd backend
alembic upgrade --sql head
popd
```

- Also run the migration smoke pytest that runs Alembic against a temporary sqlite DB if present:

```bash
pytest -q backend/tests/test_migration_smoke.py::test_alembic_smoke
```

5. Apply migration in staging and verify
---------------------------------------
- Run migrations on a staging DB and verify application behavior and that `model_metadata` constraints hold.
- Ensure your application can still load models and sidecars after the migration.

6. Apply to production (maintenance window recommended)
------------------------------------------------------
- Apply the same steps during a maintenance window: backup, apply dedupe (if needed), run alembic upgrade, deploy application.
- Monitor logs for artifact load failures and be ready to roll back using DB backups.

7. Post-migration checks
------------------------
- Validate that every model has a sidecar with `feature_list` and `feature_list_checksum`.
- If artifact signing is enabled, ensure `MODEL_ARTIFACT_SIGNING_KEY` is set in the runtime environment and perform spot checks of signature verification.

Notes
-----
- The migration scripts in `backend/alembic/versions` may include merge-style down-revisions to accommodate multiple heads in CI smoke tests. Review the migration graph before applying to production.
- Prefer running the CI `migration_safety` workflow on PRs that touch alembic or DB-related code.
