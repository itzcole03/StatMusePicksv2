#!/usr/bin/env python3
"""
Run a simple TimescaleDB vs regular table benchmark for player_stats-like data.

Creates two tables in the target Postgres DB on localhost:5433:
- player_stats_regular
- player_stats_hypertable (hypertable on game_date)

Populates synthetic rows and runs a few representative time-series queries measuring execution time.

Usage: python backend/scripts/run_timescale_benchmark.py --rows 100000
"""
import argparse
import random
import time
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import execute_batch

DEFAULT_ROWS = 100000
CHUNK_SIZE = 2000


def connect(
    dbname="statmuse_timescale",
    host="localhost",
    port=5433,
    user="postgres",
    password="postgres",
):
    conn = psycopg2.connect(
        dbname=dbname, user=user, password=password, host=host, port=port
    )
    conn.autocommit = True
    return conn


def setup_tables(conn):
    cur = conn.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS player_stats_regular (
        id SERIAL PRIMARY KEY,
        player_id INTEGER NOT NULL,
        game_id INTEGER NOT NULL,
        stat_type TEXT NOT NULL,
        value DOUBLE PRECISION NOT NULL,
        game_date DATE NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS player_stats_hypertable (
        id SERIAL PRIMARY KEY,
        player_id INTEGER NOT NULL,
        game_id INTEGER NOT NULL,
        stat_type TEXT NOT NULL,
        value DOUBLE PRECISION NOT NULL,
        game_date DATE NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """
    )

    # create hypertable if not exists
    try:
        cur.execute(
            "SELECT create_hypertable('player_stats_hypertable','game_date', if_not_exists => TRUE);"
        )
    except Exception:
        # Some versions use if_not_exists := true
        try:
            cur.execute(
                "SELECT create_hypertable('player_stats_hypertable','game_date', if_not_exists := true);"
            )
        except Exception:
            # ignore if cannot create (maybe already hypertable)
            pass

    # Indexes used in production-like workloads
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_regular_player_game_date ON player_stats_regular (player_id, game_date);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_hypertable_player_game_date ON player_stats_hypertable (player_id, game_date);"
    )
    cur.close()


def clear_tables(conn):
    cur = conn.cursor()
    cur.execute("TRUNCATE player_stats_regular RESTART IDENTITY;")
    cur.execute("TRUNCATE player_stats_hypertable RESTART IDENTITY;")
    cur.close()


def generate_row(player_id, game_id, stat_type, base_date):
    # synthetic value around a player-specific mean
    mean = 10 + (player_id % 10) * 2
    value = random.gauss(mean, 5)
    game_date = (base_date - timedelta(days=game_id % 365)).date()
    return (player_id, game_id, stat_type, float(value), game_date)


def populate(conn, rows):
    cur = conn.cursor()
    total = rows
    players = 500  # number of unique players to simulate
    stat_types = ["points", "rebounds", "assists"]
    base_date = datetime.now(timezone.utc)

    insert_sql = "INSERT INTO {table} (player_id, game_id, stat_type, value, game_date) VALUES (%s,%s,%s,%s,%s)"

    for table in ("player_stats_regular", "player_stats_hypertable"):
        print(f"Populating {table} with {rows} rows...")
        start = time.time()
        inserted = 0
        while inserted < total:
            batch = []
            for i in range(min(CHUNK_SIZE, total - inserted)):
                player_id = random.randint(1, players)
                game_id = random.randint(1, 2000)
                stat = random.choice(stat_types)
                batch.append(generate_row(player_id, game_id, stat, base_date))
            execute_batch(cur, insert_sql.format(table=table), batch)
            inserted += len(batch)
            if inserted % (CHUNK_SIZE * 5) == 0:
                print(f"  inserted {inserted}/{total} rows...")
        elapsed = time.time() - start
        print(f"  finished inserting {total} rows into {table} in {elapsed:.2f}s")

    cur.close()


def run_queries(conn):
    cur = conn.cursor()
    # sample player and date range
    player_id = random.randint(1, 500)
    today = datetime.now(timezone.utc).date()
    thirty_days_ago = today - timedelta(days=30)

    queries = [
        (
            "Regular: avg value for player last 30 days",
            "SELECT AVG(value) FROM player_stats_regular WHERE player_id = %s AND game_date >= %s",
            (player_id, thirty_days_ago),
        ),
        (
            "Hypertable: avg value for player last 30 days",
            "SELECT AVG(value) FROM player_stats_hypertable WHERE player_id = %s AND game_date >= %s",
            (player_id, thirty_days_ago),
        ),
        (
            "Regular: range scan by date",
            "SELECT player_id, AVG(value) FROM player_stats_regular WHERE game_date BETWEEN %s AND %s GROUP BY player_id ORDER BY AVG(value) DESC LIMIT 10",
            (thirty_days_ago, today),
        ),
        (
            "Hypertable: range scan by date",
            "SELECT player_id, AVG(value) FROM player_stats_hypertable WHERE game_date BETWEEN %s AND %s GROUP BY player_id ORDER BY AVG(value) DESC LIMIT 10",
            (thirty_days_ago, today),
        ),
    ]

    results = []
    for label, sql, params in queries:
        start = time.time()
        cur.execute(sql, params)
        rows = cur.fetchall()
        elapsed = time.time() - start
        print(f"{label}: {elapsed:.4f}s, rows={len(rows)}")
        results.append((label, elapsed, len(rows)))

    cur.close()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows", type=int, default=DEFAULT_ROWS, help="Total rows to insert per table"
    )
    args = parser.parse_args()

    conn = connect()
    setup_tables(conn)
    clear_tables(conn)
    populate(conn, args.rows)
    results = run_queries(conn)
    print("\nBenchmark results summary:")
    for r in results:
        print(f"- {r[0]}: {r[1]:.4f}s rows={r[2]}")

    conn.close()


if __name__ == "__main__":
    main()
