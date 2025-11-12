# Timescale Tuning Notes

This document contains recommended tuning parameters, index and compression
settings, and guidance for picking `chunk_time_interval` and continuous
aggregate policies for the `player_stats` hypertable.

1) Chunk sizing
   - Goal: keep chunk physical size in a reasonable range (e.g., 100MB - 1GB)
   - Use `chunk_time_interval` to control chunk size based on event density.
   - Recommendation: start with `7 days` for high-volume ingest (many rows per day),
     otherwise `30 days` for lower-volume datasets.

2) Indexing
   - Keep a primary index on `game_id` (if unique). Create low-cardinality
     secondary indexes with `CONCURRENTLY` to avoid locks.
   - Example indexes:
     - `CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_player_game_date ON player_stats (player_id, game_date);`
     - Consider partial indexes for frequent queries (e.g., WHERE stat_type='points').

3) Compression
   - Use compression for older historical chunks to save storage and improve
     IO for scans on aggregated queries.
   - Example:
     - `ALTER TABLE player_stats SET (timescaledb.compress, timescaledb.compress_segmentby = 'player_id');`
     - `SELECT add_compression_policy('player_stats', INTERVAL '90 days');`
   - Test compression ratio on staging before enabling in production.

4) Continuous Aggregates
   - For heavy aggregation queries (e.g., daily player averages), create continuous
     aggregates to pre-compute results:
     ```sql
     CREATE MATERIALIZED VIEW player_daily_avg WITH (timescaledb.continuous) AS
     SELECT time_bucket('1 day', game_date) AS day, player_id, AVG(value) AS avg_value
     FROM player_stats
     GROUP BY day, player_id;
     SELECT add_continuous_aggregate_policy('player_daily_avg', start_offset => INTERVAL '7 days', end_offset => INTERVAL '1 day', schedule_interval => INTERVAL '1 day');
     ```

5) Monitoring
   - Monitor `timescaledb_information.hypertable` and `timescaledb_information.chunks` for chunk counts and sizes.
   - Alert when chunk counts grow unexpectedly or when query latency increases.

6) Production checks
   - Run `EXPLAIN (ANALYZE, BUFFERS)` for sample queries pre/post conversion.
   - Verify `pg_stat_user_tables` and `pg_stat_user_indexes` for scanning patterns.

7) Rollout plan reference
   - See `backend/TIMESCALE_ROLLOUT.md` for full blue/green and cutover steps.
