"""Generate training datasets for players with sufficient history.

Usage:
  python scripts/generate_datasets.py --seasons 2024-25,2023-24 --min-games 50 --name points_dataset

This script will:
 - query the DB for player_ids with >= min_games in `player_stats` (sync query)
 - resolve player names via `nba_stats_client.fetch_all_players()`
 - call `generate_training_data` for each player and collect rows
 - perform per-player deterministic time split and export Parquet datasets
 - create a dataset_versions manifest via `dataset_versioning.create_dataset_version`

This is best-effort: requires DB connectivity and `pyarrow` installed for Parquet output.
"""

import argparse
import os
from typing import List

import pandas as pd

from backend.services import dataset_versioning, nba_stats_client
from backend.services import training_data_service as tds

try:
    from sqlalchemy import create_engine, text
except Exception:
    create_engine = None


def _make_sync_db_url(async_url: str) -> str:
    if async_url.startswith("sqlite+aiosqlite"):
        return async_url.replace("sqlite+aiosqlite", "sqlite")
    if "+asyncpg" in async_url:
        return async_url.replace("+asyncpg", "")
    return async_url


def query_players_with_min_games(db_url: str, min_games: int, stat: str) -> List[int]:
    sync_url = _make_sync_db_url(db_url)
    if create_engine is None or not sync_url:
        raise RuntimeError("No sync DB engine available or DATABASE_URL unset")
    engine = create_engine(sync_url)
    # Prefer players who have recorded games (join to games) and match the requested stat
    sql = text(
        "SELECT ps.player_id FROM player_stats ps JOIN games g ON ps.game_id = g.id WHERE ps.stat_type = :stat GROUP BY ps.player_id HAVING COUNT(*) >= :min_games"
    )
    out = []
    with engine.begin() as conn:
        try:
            res = conn.execute(sql, {"min_games": min_games, "stat": stat})
            for row in res:
                out.append(int(row[0]))
        except Exception as e:
            raise
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--seasons", type=str, default="2024-25", help="Comma-separated seasons list"
    )
    p.add_argument("--min-games", type=int, default=50)
    p.add_argument("--name", type=str, default="points_dataset")
    p.add_argument("--stat", type=str, default="points")
    p.add_argument(
        "--db-only", action="store_true", help="Use only local DB (no network calls)"
    )
    p.add_argument("--output-dir", type=str, default="backend/data/datasets")
    args = p.parse_args()

    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL must be set in environment")

    print(
        "Querying DB for players with >=", args.min_games, "games for stat", args.stat
    )
    pids = query_players_with_min_games(db_url, args.min_games, args.stat)
    print("Found", len(pids), "players")

    # build id -> name map
    id_to_name = {}
    # Prefer reading `players` table from the sync DB to avoid external nba_api calls
    try:
        sync_url = _make_sync_db_url(db_url)
        engine2 = create_engine(sync_url)
        placeholder = ",".join([str(int(x)) for x in pids]) if pids else "0"
        q = text(
            f"SELECT id, full_name, fullName, display_name FROM players WHERE id IN ({placeholder})"
        )
        with engine2.begin() as conn:
            res = conn.execute(q)
            for row in res:
                pid = int(row[0])
                name = None
                for v in row[1:]:
                    if v:
                        name = v
                        break
                if name:
                    id_to_name[pid] = name
    except Exception:
        # fallback to nba_api cached list
        players_list = nba_stats_client.fetch_all_players() or []
        id_to_name = {
            int(p.get("id")): p.get("full_name")
            or p.get("fullName")
            or p.get("display_name")
            for p in players_list
        }

    all_rows = []
    for pid in pids:
        name = id_to_name.get(pid)
        if not name:
            print("Skipping pid", pid, "name unknown")
            continue
        try:
            print("Generating for", name)
            if args.db_only:
                # Build from local DB (player_stats + games join) only
                db_url_sync = _make_sync_db_url(db_url)
                from sqlalchemy import create_engine, text

                eng = create_engine(db_url_sync)
                q = text(
                    "SELECT g.game_date as game_date, ps.value as target FROM player_stats ps JOIN games g ON ps.game_id = g.id WHERE ps.player_id = :pid AND ps.stat_type = :stat ORDER BY g.game_date"
                )
                rows = []
                with eng.begin() as conn:
                    res = conn.execute(q, {"pid": pid, "stat": args.stat})
                    for r in res:
                        # r may be positional or mapping
                        try:
                            gd = r["game_date"]
                            tgt = r["target"]
                        except Exception:
                            gd = r[0]
                            tgt = r[1]
                        rows.append({"player": name, "game_date": gd, "target": tgt})
                import pandas as _pd

                if not rows:
                    raise ValueError(f"not enough games for player {name} (found 0)")
                df = _pd.DataFrame(rows)
            else:
                # pass pid directly to avoid name-based network lookups
                try:
                    df = tds.generate_training_data(
                        name, stat=args.stat, seasons=seasons, min_games=args.min_games
                    )
                except ValueError:
                    # retry without restricting to specific seasons (use all available history)
                    df = tds.generate_training_data(
                        name,
                        stat=args.stat,
                        seasons=None,
                        min_games=args.min_games,
                        pid=pid,
                    )
                except Exception as e:
                    # Network or nba_api may be unavailable — fall back to building
                    # training rows from the local DB (player_stats + games join).
                    print(
                        "Warning: generate_training_data failed for",
                        name,
                        "falling back to DB method:",
                        str(e),
                    )
                    # Build from DB if possible
                    db_url_sync = _make_sync_db_url(db_url)
                    try:
                        from sqlalchemy import create_engine, text

                        eng = create_engine(db_url_sync)
                        q = text(
                            "SELECT g.game_date as game_date, ps.value as target FROM player_stats ps JOIN games g ON ps.game_id = g.id WHERE ps.player_id = :pid AND ps.stat_type = :stat ORDER BY g.game_date"
                        )
                        rows = []
                        with eng.begin() as conn:
                            res = conn.execute(q, {"pid": pid, "stat": args.stat})
                            for r in res:
                                try:
                                    gd = r["game_date"]
                                    tgt = r["target"]
                                except Exception:
                                    gd = r[0]
                                    tgt = r[1]
                                rows.append(
                                    {"player": name, "game_date": gd, "target": tgt}
                                )
                        import pandas as _pd

                        if not rows:
                            raise
                        df = _pd.DataFrame(rows)
                    except Exception:
                        raise
            # attach player column if missing
            if "player" not in df.columns:
                df["player"] = name
            all_rows.append(df)
        except Exception as e:
            print("Skipping", name, "error:", str(e))
            continue

    if not all_rows:
        raise RuntimeError("No training rows generated for any players")

    big_df = pd.concat(all_rows, ignore_index=True)
    print("Total rows generated:", len(big_df))

    train_df, val_df, test_df = tds.per_player_time_split(
        big_df, player_col="player", date_col="game_date"
    )

    manifest = dataset_versioning.create_dataset_version(
        args.name,
        ",".join(seasons),
        train_df,
        val_df,
        test_df,
        output_dir=args.output_dir,
    )
    print("Wrote dataset manifest:", manifest.get("manifest"))


if __name__ == "__main__":
    main()
