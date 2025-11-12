# TimescaleDB Production Rollout Plan

Purpose
-------
This runbook describes a safe, best-practice approach to introducing TimescaleDB (hypertables) into production for time-series data (e.g., `player_stats`). It covers options (managed vs extension), schema migration strategies, performance tuning, backups, monitoring, rollback, and a staged rollout plan aligned with the repository roadmap.

Assumptions
-----------
- Production uses PostgreSQL (version >= 14). Installing extensions in production may require managed service support or DBA approval.
- We have a staging environment where we can run TimescaleDB (already provisioned locally for benchmarking).
- Migrations are applied via Alembic; we will add migration scripts and CI checks.

High-level options
------------------
1. Managed Timescale (recommended): use Timescale Cloud or your DB provider's managed offering that supports the `timescaledb` extension. Simplifies upgrades, HA, and operational burden.
2. Install extension on existing Postgres instance (requires DBA access): install `timescaledb` extension and run conversion steps.

Rollout Phases
--------------
Phase A — Planning & Validation (non-prod)
- Create a staging DB with the same major Postgres version as production and enable `timescaledb`.
- Run representative benchmarks (we added `backend/scripts/run_timescale_benchmark.py`).
- Collect `EXPLAIN (ANALYZE, BUFFERS)` for critical queries and compare.
- Decide chunking strategy (time interval) based on data volume and retention (e.g., 7 days, 30 days, or 1 month chunks).

Phase B — Migration Preparation
- Add Alembic migration(s) to repo that: create the hypertable conversion step as idempotent SQL and create production-grade indexes (partial/covering indexes where needed).
- Example migration steps (pseudocode / SQL):

```sql
-- create hypertable (idempotent)
SELECT create_hypertable('player_stats', 'game_date', if_not_exists => TRUE);

-- create indexes used in queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_player_game_date ON player_stats (player_id, game_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_game_date ON player_stats (game_date);
```

- Important: use `CONCURRENTLY` for index creation to avoid long locks on large tables.
- Add a feature-flag or config flag (env var) `USE_HYPERTABLES=true/false` so application can be toggled to query hypertables if needed during rollout.

Phase C — Staged Data Migration (if converting existing table)
- Two options:
  1. In-place conversion (fast path): run `create_hypertable('player_stats', 'game_date', if_not_exists => true)` on the existing table. This converts it in-place — test on staging first.
  2. Blue/Green migration (safer): create `player_stats_new` hypertable, backfill data in batches, switch application reads/writes to new table during a short maintenance window, then drop old table.

Blue/Green migration recommended steps (safe, reversible):

1. Create `player_stats_new` table with same schema and convert to hypertable.
2. Backfill historical data in chunks (SQL `INSERT INTO player_stats_new SELECT * FROM player_stats WHERE game_date < '...'` in transactions sized to avoid long locks).
3. Start replicating new writes: either by enabling streaming replication, using logical replication, or add DB trigger on original table that copies newly inserted rows to `player_stats_new` until cutover.
4. Validate counts and checksums between source and target (row counts, aggregates).
5. Schedule short maintenance window for cutover: stop application writers (or set app to read-only), apply final incremental copy, atomically rename tables (`ALTER TABLE player_stats RENAME TO player_stats_old; ALTER TABLE player_stats_new RENAME TO player_stats;`).
6. Monitor for errors; if rollback needed, reverse renames and resume.

Phase D — Post-Migration Tuning & Monitoring
- Configure chunk_time_interval: pick a reasonable interval (e.g., 7 days or 30 days) because chunk size affects query performance and maintenance cost. Use `set_chunk_time_interval()` or pass `chunk_time_interval` during hypertable creation.
- Create continuous aggregates for heavy aggregation queries (e.g., daily player averages) and refresh policies.
- Configure retention / compression policies for older chunks:
  - `SELECT add_compression_policy('player_stats', INTERVAL '90 days');`
  - Test compression on staging first.

Operational Considerations
--------------------------
- Backups: ensure `pg_dump` / PITR (WAL archiving) is set and tested. When using Timescale, backups are still PostgreSQL-native.
- Monitoring: track chunk counts, hypertable size, index bloat, and query latencies. Timescale provides telemetry; integrate into Prometheus/Grafana.
- Maintenance: schedule periodic `VACUUM` / `ANALYZE`, monitor autovacuum and plan for index reindexing if bloat occurs.

CI / Deployment Integration
-------------------------
- Add Alembic migration smoke tests in CI (already added) to run migrations against a disposable Postgres instance to verify idempotence.
- Deploy migration first to a staging environment and run full test-suite.
- Use feature flag `USE_HYPERTABLES` to minimize production risk: when `false`, application continues to use legacy queries/tables; when `true`, it uses hypertable-optimized queries.

Rollback Plan
-------------
- If conversion used in-place hypertable creation, rollback means:
  - If catastrophic, restore from backup snapshot taken prior to migration.
  - For targeted issues (index problems), drop problematic index or adjust config.
- For Blue/Green, rollback is trivial: rename tables back to their original names and resume traffic to the old table.

Verification Checklist (post-cutover)
-----------------------------------
- [ ] Row counts match between old and new (if backfilled).
- [ ] Critical queries latency within expected thresholds.
- [ ] CI smoke tests pass against staging hypertable.
- [ ] Continuous aggregates contain expected values.
- [ ] Backups succeed and recovery tested.
- [ ] Monitoring alerts configured for hypertable-specific metrics.

Security & Compliance
---------------------
- Ensure extension installation is approved by DBAs and security team. Installing server extensions may be restricted on managed DB services.
- Maintain least-privilege for any scripts that perform data copy or schema changes.

Example Commands & SQL
----------------------
Create hypertable (idempotent example placed in an Alembic migration):

```sql
-- backend/alembic/versions/xxxx_create_player_stats_hypertable.py
-- inside upgrade():
EXECUTE "SELECT create_hypertable('player_stats','game_date', if_not_exists => TRUE);";
-- create indexes concurrently to avoid locks
EXECUTE "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_player_game_date ON player_stats (player_id, game_date);";
```

Blue/Green incremental copy (example pattern):

```sql
-- copy in batches (adjust WHERE clause and LIMIT as needed)
INSERT INTO player_stats_new (player_id, game_id, stat_type, value, game_date, created_at)
SELECT player_id, game_id, stat_type, value, game_date, created_at
FROM player_stats
WHERE id > $last_id
ORDER BY id
LIMIT 10000;
```

Cutover rename (during maintenance window):

```sql
BEGIN;
ALTER TABLE player_stats RENAME TO player_stats_old;
ALTER TABLE player_stats_new RENAME TO player_stats;
COMMIT;
```

Runbook Snippets (commands)
---------------------------
Start a disposable Postgres with Timescale for CI/staging:
```powershell
docker run --name temp_timescale -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=temp_db -p 5433:5432 -d timescale/timescaledb:latest-pg15
docker exec temp_timescale psql -U postgres -d temp_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

Apply migrations in CI-style smoke:
```powershell
alembic -c backend/alembic.ini upgrade head
pytest -q backend/tests/test_db_health.py::test_db_health_sqlite
```

Notes & Risks
-------------
- Converting very large tables in-place can be disruptive; prefer Blue/Green for large datasets.
- Compression and continuous aggregates can significantly reduce storage and speed up queries — test before enabling in production.
- Chunk sizing is critical; monitor chunk count and adjust `chunk_time_interval` as needed.

Contacts
--------
- DB Admin / Platform: [add names/emails]
- Engineering owner: [add name]

References
----------
- Timescale docs: https://docs.timescale.com
- Script: `backend/scripts/run_timescale_benchmark.py` (local benchmark harness)
 
## Expanded Production Runbook (commands, verification, DBA checklist)

This section contains actionable commands, safety checks, and verification queries to follow when preparing a staging or production rollout.

Pre-flight checklist (run on staging with production-like data):
- Take a full logical backup (pg_dump) and a filesystem snapshot if available.
- Ensure a tested restore is available and recovery point objectives (RPO) are understood.
- Confirm DBA approval for extension install or Timescale-managed offering.
- Notify stakeholders and schedule a maintenance window for cutover if doing in-place conversion.

Enable Timescale extension (staging example):

```powershell
# start a disposable timescaledb container (staging)
docker run --name temp_timescale -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=temp_db -p 5433:5432 -d timescale/timescaledb:latest-pg15
docker exec temp_timescale psql -U postgres -d temp_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
```

Idempotent Alembic invocation with log capture and FORCE guard (example CI/local):

```powershell
mkdir -p logs
# export FORCE_PLAYER_STATS_HT=1 to skip row-count guards in the migration if you have DBA approval
export FORCE_PLAYER_STATS_HT=0
alembic -c backend/alembic.ini upgrade head 2>&1 | tee logs/alembic_full_upgrade.log
```

Recommended safe hypertable conversion flow (blue/green preferred for large tables):

1) Create new hypertable: create a copy and convert

```sql
-- run in psql connected to the staging DB
CREATE TABLE player_stats_new (LIKE player_stats INCLUDING ALL);
SELECT create_hypertable('player_stats_new', 'game_date', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
```

2) Backfill in small batches to avoid long locks (example batching loop):

```sql
-- run repeated INSERT ... SELECT with WHERE conditions to chunk by id or date
INSERT INTO player_stats_new (player_id, game_id, stat_type, value, game_date, created_at)
SELECT player_id, game_id, stat_type, value, game_date, created_at
FROM player_stats
WHERE id > $last_id
ORDER BY id
LIMIT 10000;
```

3) Verify row parity and basic aggregates before cutover:

```sql
-- row counts
SELECT COUNT(*) FROM player_stats; -- source
SELECT COUNT(*) FROM player_stats_new; -- target

-- checksums (sampled by player or date range)
SELECT player_id, COUNT(*), SUM(value) FROM player_stats WHERE game_date >= '2024-01-01' GROUP BY player_id ORDER BY player_id LIMIT 10;
SELECT player_id, COUNT(*), SUM(value) FROM player_stats_new WHERE game_date >= '2024-01-01' GROUP BY player_id ORDER BY player_id LIMIT 10;
```

4) Cutover (during maintenance window):

```sql
BEGIN;
ALTER TABLE player_stats RENAME TO player_stats_old;
ALTER TABLE player_stats_new RENAME TO player_stats;
COMMIT;

-- optional: create additional concurrent indexes on the new table if needed
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_player_game_date ON player_stats (player_id, game_date);
```

5) Post-cutover verification (run immediately and in the following hours):

```sql
-- sanity checks
SELECT COUNT(*) FROM player_stats;
SELECT COUNT(*) FROM player_stats_old;

-- run representative queries with EXPLAIN ANALYZE
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM player_stats WHERE player_id = 123 ORDER BY game_date DESC LIMIT 10;

-- validate continuous aggregates if configured
REFRESH MATERIALIZED VIEW CONCURRENTLY player_daily_avg;
SELECT * FROM player_daily_avg WHERE player_id = 123 ORDER BY day DESC LIMIT 5;
```

Compression and continuous aggregate examples:

```sql
-- add compression policy for data older than 90 days
ALTER TABLE player_stats SET (timescaledb.compress, timescaledb.compress_segmentby = 'player_id');
SELECT add_compression_policy('player_stats', INTERVAL '90 days');

-- create a continuous aggregate (daily averages)
CREATE MATERIALIZED VIEW player_daily_avg WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', game_date) AS day, player_id, AVG(value) AS avg_value
FROM player_stats
GROUP BY day, player_id;

SELECT add_continuous_aggregate_policy('player_daily_avg', start_offset => INTERVAL '7 days', end_offset => INTERVAL '1 day', schedule_interval => INTERVAL '1 day');
```

DBA checklist before running migration in production:
- Verify backups and WAL archiving are functional; take a snapshot before migration.
- Confirm extension installation method and required privileges; document approval.
- Review migration runtime estimate on staging for data volumes comparable to production.
- Confirm index creation plan (CONCURRENTLY) and expected maintenance cost.
- Communicate maintenance window and rollback steps to on-call and stakeholders.
- Test restore from backup to an isolated environment and validate the application against it.

Monitoring and alerting recommendations:
- Add Prometheus/Grafana dashboards for hypertable size, chunk count, compression ratio, and index bloat.
- Alert if chunk count grows unexpectedly or if query latency for critical endpoints increases by >20%.

Rollback options (summary):
- If using Blue/Green: rename tables back and resume traffic to the old table.
- If in-place: restore from pre-migration backup snapshot.

Contact info & approvals
- Add DBA and platform team contact info here and include the runbook link in the change ticket.

---

If you'd like, I can also generate a small `scripts/` helper that automates batch backfill and parity checks (PowerShell and SQL), or add a pre-flight CI job that runs the Alembic migration in a dry-run mode and validates expected SQL statements. Which would you prefer next?
