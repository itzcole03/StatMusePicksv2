This draft PR adds Alembic validation and hardening to prevent migration conflicts, plus CI smoke tests.

Summary of changes:

- Added Alembic validator script: `backend/scripts/check_alembic_graph.py`.
- Set `ALEMBIC_RUNNING` in `backend/alembic/env.py` to avoid app code running `create_all()` during migrations.
- Made migrations idempotent by checking existing tables/indexes in:
  - `backend/alembic/versions/0001_initial.py`
  - `backend/alembic/versions/0002_add_game_stats_predictions.py`
  - `backend/alembic/versions/0003_add_indexes.py`
  - `backend/alembic/versions/0006_add_player_stats_stattype_index.py`
  - `backend/alembic/versions/0007_add_team_stats.py`
- Guarded `Base.metadata.create_all()` in `backend/services/data_ingestion_service.py` to skip when Alembic is running.
- Added PR-time Alembic validation workflow: `.github/workflows/alembic-validate.yml`.
- Added Postgres smoke workflow: `.github/workflows/alembic-migration-smoke.yml`.
- Added docs and guidance:
  - `CONTRIBUTING.md` (migration workflow)
  - `docs/alembic_migration_conflicts_report.md`
- Pinned backend dependencies: `backend/requirements.lock`.

Why: Prevent duplicate DDL errors during migrations, catch migration graph issues early in PR CI, and provide guidance for future migration authors.

Checklist
- [ ] Run CI (PR) and review any failures
- [ ] Confirm base branch is `main` (switch to `master` if necessary)
- [ ] Decide index-management policy (models vs migrations) and follow up if needed

Notes
- If `gh` is not authenticated locally, `gh pr create` will fail; you can push the branch and open the PR on GitHub web instead.
