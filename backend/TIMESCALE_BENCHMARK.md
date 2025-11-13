# TimescaleDB Local Benchmark

Summary
-------
This document records a quick local benchmark comparing a regular `player_stats` table versus a TimescaleDB hypertable (`player_stats_hypertable`). The goal is a lightweight, reproducible check to see if hypertables provide latency improvements for typical time-series queries.

What I ran
-----------
- Started a Timescale container on `localhost:5433` (image `timescale/timescaledb:latest-pg15`).
- Created two tables: `player_stats_regular` and `player_stats_hypertable` and converted the latter to a hypertable on `game_date`.
- Inserted 100,000 synthetic rows into each table (script inserts in batches).
- Executed representative queries and measured wall-clock time.

Commands
--------
Start Timescale container (if not already running):
```powershell
docker rm -f statmuse_timescale || true
docker run --name statmuse_timescale -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=statmuse_timescale -p 5433:5432 -d timescale/timescaledb:latest-pg15
docker exec statmuse_timescale psql -U postgres -d statmuse_timescale -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

Run the benchmark script (provided in repo):
```powershell
python backend/scripts/run_timescale_benchmark.py --rows 100000
```

Sample Results (one run)
------------------------
- Insert 100k rows into `player_stats_regular`: ~55.5s
- Insert 100k rows into `player_stats_hypertable`: ~55.0s
- Regular: avg value for player last 30 days: 0.0037s
- Hypertable: avg value for player last 30 days: 0.0013s
- Regular: range scan by date: 0.0110s
- Hypertable: range scan by date: 0.0076s

Interpretation & Next Steps
---------------------------
- Hypertable queries were faster on these micro-benchmarks (roughly 1.5–2.5x faster for sampled queries). Bulk insert times similar for this scale and insertion method.
- Recommended next actions:
  - Run larger-scale benchmarks (500k–2M rows) to validate scaling behavior.
  - Add `EXPLAIN (ANALYZE, BUFFERS)` on slow queries to inspect planner choices and IO.
  - Profile typical production query shapes (time windows, number of players, aggregation granularity).
  - If consistent gains are observed, plan a production rollout with migrations to create hypertables, migration/rollback steps, and backup/restore testing.

Notes
-----
- This is a local, synthetic benchmark. Results will vary based on data distribution, hardware, and query shapes. Use the script as a starting point and adapt queries to match production workloads.

File added by: benchmark script run on Nov 11, 2025
