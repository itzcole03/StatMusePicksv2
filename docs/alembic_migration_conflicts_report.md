# Alembic Migration Conflicts Scan Report

Generated: 2025-11-12

Summary
- Scanned migrations and models for common patterns that cause migration conflicts (duplicate DDL) such as `index=True` on model Columns vs explicit `op.create_index` in migrations, and direct `Base.metadata.create_all()` calls.

Findings

1) Model columns that declare `index=True` (these create indexes via metadata)
- `backend/models/team_stat.py`:
  - `id` (index=True)
  - `team` (index=True)
  - `season` (index=True)
- `backend/models/projection.py`:
  - `id`, `player_id`, `stat` (index=True)
- `backend/models/prediction.py`:
  - `id`, `player_id`, `stat_type`, `game_id` (index=True)
- `backend/models/player_stat.py`:
  - `id`, `player_id`, `game_id`, `stat_type` (index=True)
- `backend/models/player.py`:
  - `id`, `nba_player_id`, `name` (index=True)
- `backend/models/model_metadata.py`:
  - `id`, `name` (index=True)
- `backend/models/game.py`:
  - `id`, `game_date` (index=True)

Risk: When migrations explicitly `op.create_index(...)` for the same columns, DBs (especially SQLite) may raise "index already exists" errors during migration runs.

2) Migrations that create explicit indexes/tables
- `backend/alembic/versions/0003_add_indexes.py` — creates `ix_player_stats_player_id_game_id_created_at` and `ix_predictions_player_id_created_at` (now guarded)
- `backend/alembic/versions/0006_add_player_stats_stattype_index.py` — creates `ix_player_stats_player_id_game_id_stat_type` (now guarded)
- `backend/alembic/versions/0007_add_team_stats.py` — creates `team_stats` table (now guarded)
- `backend/alembic/versions/0002_add_game_stats_predictions.py` — creates tables `games`, `player_stats`, `predictions` (now guarded)
- `backend/alembic/versions/0001_initial.py` — creates `players`, `projections`, `model_metadata` (now guarded)

3) Direct metadata.create_all() calls
- `backend/services/data_ingestion_service.py` — calls `Base.metadata.create_all(engine)` in two places on sync engine; these are now guarded to skip when `ALEMBIC_RUNNING` is set.
- Tests (various `backend/tests/*`) call `Base.metadata.create_all(engine)` intentionally to set up test DBs — these are fine.

Recommendations

- Prefer one source of truth for DDL: if using SQLAlchemy models + metadata autogenerate, avoid duplicating index creation manually in migrations for the same columns. If explicit index creation is preferred, set `index=False` on model Column definitions to avoid auto-created indexes.

- Keep guarded checks in migrations (inspector checks) where necessary to be idempotent and safe across dialects (SQLite vs Postgres). The repo now includes such guards in several migrations.

- Avoid calling `Base.metadata.create_all()` during Alembic runs (we set `ALEMBIC_RUNNING=1` in `alembic/env.py` and guarded `create_all` calls in ingestion code). Continue this pattern for any other modules that might auto-create tables when imported by Alembic.

- CI: keep both quick SQLite validation and a Postgres smoke test (already added) to catch dialect-specific SQL (Timescale/extension SQL) that SQLite cannot surface.

Action items for review
- Review model columns that set `index=True` and decide whether to rely on migrations to create the index (set `index=False` in models) or keep as-is and remove duplicate `op.create_index` from migrations.
- Optionally scan for `index=` in other code paths and for any `op.execute()` with raw SQL that may be Postgres/Timescale-specific.

Scan details
- Commands run locally (for reproducibility):
  - `rg "index=True" backend -n` (ripgrep used via grep_search)
  - `rg "op.create_index" backend/alembic/versions -n`

If you'd like, I can:
- Automatically replace duplicate `op.create_index` calls with guards (already implemented for several migrations) for the remaining ones.
- Create a small CI check that reports migration/model overlaps as a pre-commit check (e.g., script that scans for same index names in models vs migration files).


