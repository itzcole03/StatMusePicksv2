# TimescaleDB Staging Setup & Benchmark Notes

This document describes a lightweight way to run TimescaleDB locally for benchmarking time-series workloads and to test hypertables for `player_stats`.

## Start TimescaleDB (local staging)

From the repository root:

PowerShell:

```pwsh
docker compose -f docker-compose.timescale.yml up -d
Start-Sleep -Seconds 5
```

Bash:

```bash
docker compose -f docker-compose.timescale.yml up -d
sleep 5
```

The container exposes Postgres on port `5433` so it won't collide with the dev Postgres used by `docker-compose.dev.yml`.

## Create Timescale extension and hypertable

Once the DB is up, create the `timescaledb` extension and convert `player_stats` (or another table) into a hypertable.

PowerShell (psql):

```pwsh
$env:PGPASSWORD='postgres'
psql -h localhost -p 5433 -U postgres -d statmuse_timescale -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
# Example: create a hypertable for player_stats
psql -h localhost -p 5433 -U postgres -d statmuse_timescale -c "CREATE TABLE IF NOT EXISTS player_stats (id serial PRIMARY KEY, player_id int, game_date timestamptz, stat_type text, value numeric, created_at timestamptz DEFAULT now());"
psql -h localhost -p 5433 -U postgres -d statmuse_timescale -c "SELECT create_hypertable('player_stats', 'game_date', if_not_exists := true);"
```

Bash:

```bash
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d statmuse_timescale -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d statmuse_timescale -c "CREATE TABLE IF NOT EXISTS player_stats (id serial PRIMARY KEY, player_id int, game_date timestamptz, stat_type text, value numeric, created_at timestamptz DEFAULT now());"
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d statmuse_timescale -c "SELECT create_hypertable('player_stats', 'game_date', if_not_exists := true);"
```

## Benchmark ideas

- Bulk-insert synthetic historical player stats (e.g., 1M rows) and measure query latencies for time-range queries by `player_id`.
- Compare single-node Timescale hypertable vs standard Postgres table for the same queries.
- Use `EXPLAIN ANALYZE` to measure query plans and index usage.

## Notes

- TimescaleDB is an extension to Postgres; enabling it requires superuser rights — the Docker container image includes everything needed.
- For production, consider managed TimescaleDB (Timescale Cloud) or installing the extension into your RDS/managed Postgres if supported.
