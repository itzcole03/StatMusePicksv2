#!/usr/bin/env python3
"""
backfill_helper.py

Lightweight helper to perform a blue/green backfill from a source table to
a target table in Postgres/TimescaleDB in safe, batched increments and run
parity checks (row counts and sums) between source and target.

Usage (env var DATABASE_URL or pass --db):
  python backend/scripts/backfill_helper.py --source player_stats --target player_stats_new --batch 10000

Notes:
- Intended for staging environments. Always test on a copy of production data.
- This script performs simple batched INSERT ... SELECT operations ordered by `id`.
"""

import argparse
import os
import sys
import time
from typing import Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:
    print("Error: psycopg2 is required. Install with `pip install psycopg2-binary`.")
    raise


def connect(db_url: str):
    return psycopg2.connect(db_url)


def create_target_like_source(conn, source: str, target: str, convert_to_hypertable: bool = False, chunk_interval: Optional[str] = None):
    with conn.cursor() as cur:
        cur.execute(f"CREATE TABLE IF NOT EXISTS {target} (LIKE {source} INCLUDING ALL);")
        conn.commit()
        if convert_to_hypertable:
            # create hypertable if extension exists
            if not chunk_interval:
                chunk_interval = "INTERVAL '7 days'"
            sql = f"SELECT create_hypertable('{target}', 'game_date', if_not_exists => TRUE, chunk_time_interval => {chunk_interval});"
            try:
                cur.execute(sql)
                conn.commit()
            except Exception as e:
                print('Warning: create_hypertable failed or not supported in this DB:', e)


def batched_backfill(conn, source: str, target: str, batch: int = 10000, id_column: str = 'id'):
    last_id = 0
    total_inserted = 0
    # Determine if the source table contains a `player_id` column so we can
    # perform narrow invalidation per affected player. This is best-effort and
    # non-fatal.
    def _has_player_id(cur):
        try:
            cur.execute(f"SELECT player_id FROM {source} LIMIT 0")
            return True
        except Exception:
            return False

    try:
        with conn.cursor() as _cur:
            _supports_player_id = _has_player_id(_cur)
    except Exception:
        _supports_player_id = False
    while True:
        with conn.cursor() as cur:
            # If the source contains player_id, return it so we can invalidate
            # only the players affected by this batch. Otherwise return only the
            # id column as before.
            if _supports_player_id:
                cur.execute(f"INSERT INTO {target} (SELECT * FROM {source} WHERE {id_column} > %s ORDER BY {id_column} LIMIT %s) RETURNING {id_column}, player_id", (last_id, batch))
            else:
                cur.execute(f"INSERT INTO {target} (SELECT * FROM {source} WHERE {id_column} > %s ORDER BY {id_column} LIMIT %s) RETURNING {id_column}", (last_id, batch))
            try:
                rows = cur.fetchall()
            except psycopg2.ProgrammingError:
                # No rows returned
                rows = []
            conn.commit()
        if not rows:
            break
        inserted = len(rows)
        total_inserted += inserted
        # rows may be tuples of (id,) or (id, player_id)
        last_id = rows[-1][0]
        print(f"Inserted batch: {inserted} rows (last_id={last_id}). Total so far: {total_inserted}")
        # small sleep to yield
        time.sleep(0.1)
        # Per-player narrow invalidation: if we returned player_ids, collect
        # distinct player_ids and resolve them to player names using the
        # `players` table, then call the ingestion helper to invalidate only
        # those players' contexts. Fall back to invalidating all contexts if
        # the mapping isn't possible.
        try:
            if _supports_player_id:
                player_ids = set()
                for r in rows:
                    if len(r) >= 2 and r[1] is not None:
                        player_ids.add(r[1])

                if player_ids:
                    try:
                        # resolve ids -> names
                        with conn.cursor(cursor_factory=RealDictCursor) as cur2:
                            cur2.execute("SELECT id, name FROM players WHERE id = ANY(%s)", (list(player_ids),))
                            res = cur2.fetchall()
                        names = [row['name'] for row in res if row.get('name')]
                        if names:
                            from backend.services.data_ingestion_service import invalidate_player_contexts
                            invalidate_player_contexts(names)
                            continue  # invalidation done for this batch
                    except Exception:
                        # mapping failed; fall through to broad invalidation
                        pass

            # Broad fallback: invalidate all player_context keys (best-effort)
            try:
                from backend.services.data_ingestion_service import invalidate_all_player_contexts
                invalidate_all_player_contexts()
            except Exception:
                try:
                    from backend.services import cache as cache_module
                    cache_module.redis_delete_prefix_sync("player_context:")
                except Exception:
                    pass
        except Exception:
            # Do not let cache invalidation failures stop the backfill
            pass
    print(f"Backfill complete. Total rows inserted: {total_inserted}")


def parity_checks(conn, source: str, target: str, sum_column: Optional[str] = 'value'):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt, SUM({sum_column}) AS sumv FROM {source}")
        s = cur.fetchone()
        cur.execute(f"SELECT COUNT(*) AS cnt, SUM({sum_column}) AS sumv FROM {target}")
        t = cur.fetchone()
    print("Parity check results:")
    print(f"  source: count={s['cnt']}, sum_{sum_column}={s['sumv']}")
    print(f"  target: count={t['cnt']}, sum_{sum_column}={t['sumv']}")
    if s['cnt'] == t['cnt'] and (s['sumv'] == t['sumv'] or (s['sumv'] is None and t['sumv'] is None)):
        print("Parity: OK")
    else:
        print("Parity: MISMATCH - investigate differences (counts or sum mismatch)")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--db', default=os.environ.get('DATABASE_URL'), help='Database URL (ENV DATABASE_URL)')
    p.add_argument('--source', required=True, help='Source table name')
    p.add_argument('--target', required=True, help='Target table name')
    p.add_argument('--batch', type=int, default=10000, help='Batch size for backfill')
    p.add_argument('--id-column', default='id', help='Monotonic id column to paginate (default: id)')
    p.add_argument('--create-target', action='store_true', help='Create target table LIKE source before backfill')
    p.add_argument('--hypertable', action='store_true', help='Convert target to hypertable after creating it (requires timescaledb extension)')
    p.add_argument('--chunk-interval', default=None, help="Chunk time interval for hypertable, e.g. 'INTERVAL ''7 days''' )")
    p.add_argument('--sum-column', default='value', help='Numeric column to use for sum parity check')
    return p.parse_args()


def main():
    args = parse_args()
    if not args.db:
        print('Error: provide --db or set DATABASE_URL env var')
        sys.exit(2)
    conn = connect(args.db)
    if args.create_target:
        create_target_like_source(conn, args.source, args.target, args.hypertable, args.chunk_interval)
    batched_backfill(conn, args.source, args.target, args.batch, args.id_column)
    parity_checks(conn, args.source, args.target, args.sum_column)
    conn.close()


if __name__ == '__main__':
    main()
