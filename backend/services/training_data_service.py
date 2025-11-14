"""Training data generation helpers.

This module provides small, testable scaffolding to convert historical
game records into a feature DataFrame suitable for model training. It is
intentionally lightweight so unit tests can inject synthetic game lists
without requiring a live database engine.

Key utilities:
- `generate_samples_from_game_history` — turn a player's chronological
  game list into per-game training samples (features + target).
- `time_based_split` — deterministic, time-based train/val/test split.
- `save_dataset` — write parquet + small metadata JSON alongside it.

Notes on `games` ordering: functions expect `games` to be ordered
newest-first (index 0 is the most recent game) which matches the
`recentGames` shape used across the codebase.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import os
import json
from pathlib import Path
from datetime import datetime, timezone

from backend.services import feature_engineering


def generate_samples_from_game_history(
    player_name: str,
    games: List[Dict[str, Any]],
    lookback: int = 10,
    min_lookback: int = 1,
    stat_field: str = "statValue",
) -> pd.DataFrame:
    """Generate training samples from a player's historical games.

    Args:
        player_name: Player display name.
        games: List of game dicts, **newest-first** (most recent at index 0).
        lookback: Number of prior games to include in the context window.
        min_lookback: Minimum number of prior games required to emit a
            training sample.
        stat_field: Field name containing the numeric stat value.

    Returns:
        A pandas DataFrame with one row per training sample. Each row
        contains features computed by `feature_engineering.engineer_features`,
        plus columns: `player`, `game_date`, and `target`.
    """
    samples = []

    # compute a simple seasonAvg fallback from all available games
    vals = [g.get(stat_field) for g in games if g.get(stat_field) is not None]
    season_avg = float(pd.Series(vals).mean()) if vals else None

    n = len(games)
    for i in range(n):
        # prior games are those after index i in the newest-first list
        prior = games[i + 1 : i + 1 + lookback]
        if len(prior) < min_lookback:
            continue

        player_context = {
            "recentGames": prior,
            "seasonAvg": season_avg,
            "contextualFactors": {},
        }

        # feature_engineering.engineer_features returns a single-row DataFrame
        df_feat = feature_engineering.engineer_features(player_context)
        # attach player, date and target
        sample_row = df_feat.iloc[0].to_dict()
        sample_row["player"] = player_name
        sample_row["game_date"] = games[i].get("date")
        sample_row["target"] = games[i].get(stat_field)
        # Preserve source game identifier when available so downstream
        # integration tests and per-player splits can reference original
        # game rows. Accept common keys: 'gameId' or 'game_id'.
        sample_row["game_id"] = games[i].get("gameId") or games[i].get("game_id")
        samples.append(sample_row)

    if not samples:
        return pd.DataFrame()

    df = pd.DataFrame(samples)
    # Normalize date column to pandas datetime when possible
    try:
        df["game_date"] = pd.to_datetime(df["game_date"])
    except Exception:
        pass

    return df


def time_based_split(
    df: pd.DataFrame, date_col: str = "game_date", train_pct: float = 0.7, val_pct: float = 0.15
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split dataset into train/val/test by chronological order.

    The split is deterministic: sort by `date_col` oldest-first, then
    slice into proportions `train_pct`, `val_pct`, and remainder for test.
    """
    if df.empty:
        return df.copy(), df.copy(), df.copy()

    if date_col not in df.columns:
        raise ValueError(f"date_col '{date_col}' not found in dataframe")

    df_sorted = df.sort_values(by=date_col, ascending=True).reset_index(drop=True)
    n = len(df_sorted)
    train_end = int(n * train_pct)
    val_end = train_end + int(n * val_pct)

    train = df_sorted.iloc[:train_end].reset_index(drop=True)
    val = df_sorted.iloc[train_end:val_end].reset_index(drop=True)
    test = df_sorted.iloc[val_end:].reset_index(drop=True)
    return train, val, test


def save_dataset(df: pd.DataFrame, out_dir: str, base_name: str) -> Dict[str, Any]:
    """Save dataframe to Parquet and write a small metadata JSON.

    Returns the metadata dict written.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parquet_path = Path(out_dir) / f"{base_name}.{ts}.parquet"
    meta_path = Path(out_dir) / f"{base_name}.{ts}.meta.json"

    # Prefer Parquet when available; fall back to CSV to avoid requiring
    # heavy optional dependencies in test/dev environments.
    try:
        df.to_parquet(parquet_path, index=False)
        data_path = parquet_path
        fmt = "parquet"
    except Exception:
        # fallback
        csv_path = Path(out_dir) / f"{base_name}.{ts}.csv"
        df.to_csv(csv_path, index=False)
        data_path = csv_path
        fmt = "csv"

    meta = {
        "base_name": base_name,
        "created_at": ts,
        "rows": len(df),
        "columns": df.columns.tolist(),
        "format": fmt,
        "data_path": str(data_path),
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    # return keys for backward compatibility: `parquet` points to the
    # actual data file (may be CSV if parquet engine unavailable).
    return {"parquet": str(data_path), "meta": str(meta_path), "meta_obj": meta}


__all__ = [
    "generate_samples_from_game_history",
    "time_based_split",
    "save_dataset",
]
"""
Additional helpers: DB-backed dataset generation and versioning.
This section is an optional extension used by the CLI-based dataset
generator. Keep it after the core pure-Python helpers above so unit
tests that import the module for the pure functions remain fast.
"""

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import text

from backend import db


async def fetch_player_stat_rows(
    stat_type: str, player_ids: Optional[List[int]] = None
) -> List[Dict]:
    """Fetch rows from DB for the requested stat_type and optional players.

    Returns a list of mapping dicts suitable for constructing a DataFrame.
    """
    db._ensure_engine_and_session()
    # Basic query: join player_stats -> players -> games. Column names
    # follow the project's roadmap conventions (player_stats, players, games).
    q = """
    SELECT
        p.id AS player_id,
        p.name AS player_name,
        p.team AS player_team,
        p.position AS player_position,
        ps.game_id AS game_id,
        g.game_date AS game_date,
        g.home_team AS home_team,
        g.away_team AS away_team,
        ps.stat_type AS stat_type,
        ps.value AS stat_value
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.id
    LEFT JOIN games g ON ps.game_id = g.id
    WHERE ps.stat_type = :stat_type
    """
    params = {"stat_type": stat_type}
    if player_ids:
        # Use simple IN-clause; adapt if player_ids is large
        q += " AND ps.player_id IN :player_ids"
        params["player_ids"] = tuple(player_ids)

    async with db.engine.connect() as conn:
        result = await conn.execute(text(q), params)
        rows = [dict(r) for r in result.mappings().all()]
    return rows


def make_time_splits(df: pd.DataFrame) -> pd.DataFrame:
    """Assigns a `split` column with values 'train'|'val'|'test' per player.

    Uses a time-based split per player: oldest 70% train, next 15% val,
    most recent 15% test. If a player has too few rows, all rows go to
    'train'.
    """
    if df.empty:
        return df

    df = df.copy()
    # Ensure game_date is datetime
    df["game_date"] = pd.to_datetime(df["game_date"])

    def assign(group: pd.DataFrame) -> pd.DataFrame:
        group = group.sort_values("game_date").reset_index(drop=True)
        n = len(group)
        if n < 4:
            group["split"] = "train"
            return group
        train_end = int(n * 0.7)
        val_end = train_end + int(n * 0.15)
        # ensure at least one sample per split when possible
        if train_end < 1:
            train_end = 1
        if val_end <= train_end:
            val_end = train_end + 1
        group.loc[: train_end - 1, "split"] = "train"
        group.loc[train_end: val_end - 1, "split"] = "val"
        group.loc[val_end:, "split"] = "test"
        return group

    # Iterate groups explicitly to avoid DataFrameGroupBy.apply operating
    # on grouping columns which raises a FutureWarning in newer pandas.
    parts = []
    for pid, grp in df.groupby("player_id", sort=False):
        out_grp = assign(grp)
        parts.append(out_grp)
    if not parts:
        return df
    return pd.concat(parts, ignore_index=True)


def time_series_cv_split(
    df: pd.DataFrame,
    n_splits: int = 3,
    val_size: float = 0.15,
    test_size: float = 0.15,
    min_train_size: int = 4,
) -> List[Dict[str, pd.DataFrame]]:
    """Generate rolling time-series CV splits across players.

    This helper returns a list of folds. Each fold is a dict with
    keys: 'train', 'val', 'test' whose values are DataFrames that
    concatenate the per-player slices for that fold.

    The splitting strategy is conservative and CI-friendly: for each
    fold we slide the training window slightly forward so that later
    folds use more recent training data. Players with insufficient
    rows for a particular fold are skipped for that fold.
    """
    if df.empty:
        return []

    df = df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"])

    folds: List[Dict[str, pd.DataFrame]] = []

    # For reproducibility use the same per-player ordering
    grouped = list(df.groupby("player_id"))

    for fold_idx in range(n_splits):
        train_parts: List[pd.DataFrame] = []
        val_parts: List[pd.DataFrame] = []
        test_parts: List[pd.DataFrame] = []

        for pid, group in grouped:
            grp = group.sort_values("game_date").reset_index(drop=True)
            n = len(grp)
            if n < min_train_size:
                continue

            # compute lengths (at least 1)
            val_len = max(1, int(n * val_size))
            test_len = max(1, int(n * test_size))

            # base split anchor; slide it forward with fold index
            max_train_end = n - (val_len + test_len)
            if max_train_end < 1:
                # not enough data to have val+test, skip
                continue

            # choose train_end as an increasing anchor across folds
            # start at 50% of available and move toward max_train_end
            start_anchor = max(1, int(max_train_end * 0.5))
            if n_splits > 1:
                step = int((max_train_end - start_anchor) / max(1, n_splits - 1))
            else:
                step = 0
            train_end = start_anchor + fold_idx * step
            # ensure bounds
            train_end = min(max_train_end, max(1, train_end))

            train_slice = grp.iloc[:train_end]
            val_slice = grp.iloc[train_end : train_end + val_len]
            test_slice = grp.iloc[train_end + val_len : train_end + val_len + test_len]

            if train_slice.empty:
                continue

            train_parts.append(train_slice)
            if not val_slice.empty:
                val_parts.append(val_slice)
            if not test_slice.empty:
                test_parts.append(test_slice)

        # concat parts for this fold
        if not train_parts:
            continue
        fold = {
            "train": pd.concat(train_parts, ignore_index=True),
            "val": pd.concat(val_parts, ignore_index=True) if val_parts else pd.DataFrame(),
            "test": pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame(),
        }
        folds.append(fold)

    return folds


def compute_version_id(df: pd.DataFrame) -> str:
    """Compute a short version id from DataFrame contents and timestamp."""
    h = hashlib.sha256()
    # Use csv bytes as stable-ish representation
    h.update(df.to_csv(index=False).encode("utf-8"))
    h.update(datetime.now(timezone.utc).isoformat().encode("utf-8"))
    return h.hexdigest()[:12]


def save_dataset_version(df: pd.DataFrame, out_dir: Path, stat_type: str) -> Dict:
    """Save DataFrame as parquet and emit metadata describing the version.

    Returns metadata dict with `version_id`, `path`, `rows`, and `created_at`.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = compute_version_id(df)
    # Prefer parquet when pyarrow/fastparquet available; fall back to CSV otherwise
    filename_parquet = f"{stat_type}_dataset_{version}.parquet"
    filename_csv = f"{stat_type}_dataset_{version}.csv"
    path_parquet = out_dir / filename_parquet
    path_csv = out_dir / filename_csv
    try:
        df.to_parquet(path_parquet, index=False)
        path = path_parquet
    except Exception:
        # fallback to CSV to avoid adding a heavy dependency in dev
        df.to_csv(path_csv, index=False)
        path = path_csv

    meta = {
        "version_id": version,
        "stat_type": stat_type,
        "path": str(path),
        "rows": len(df),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(out_dir / f"{stat_type}_dataset_{version}.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


async def generate_and_save_dataset(
    stat_type: str,
    player_ids: Optional[List[int]] = None,
    out_dir: str = "backend/data/training_datasets",
    min_games_per_player: int = 50,
) -> Dict:
    """End-to-end: fetch rows, build DataFrame, split, filter and save.

    Returns the metadata for the saved dataset.
    """
    rows = await fetch_player_stat_rows(stat_type, player_ids)
    if not rows:
        raise RuntimeError("No rows fetched for stat_type={}".format(stat_type))

    df = pd.DataFrame(rows)
    # Basic sanity: ensure required columns exist
    for col in ("player_id", "game_date", "stat_value"):
        if col not in df.columns:
            raise RuntimeError(f"Missing expected column in query results: {col}")

    # Rename stat column to target for compatibility
    df = df.rename(columns={"stat_value": "target"})

    # Build per-player feature samples using the pure-Python generator which
    # relies on `feature_engineering.engineer_features`.
    samples_list: List[pd.DataFrame] = []

    # Group rows by player and prepare a newest-first games list for each
    grouped = df.groupby(["player_id", "player_name"])  # keep name for samples
    for (pid, pname), group in grouped:
        # sort newest-first by game_date
        grp = group.sort_values("game_date", ascending=False)
        # build the 'games' list expected by generate_samples_from_game_history
        games = []
        for _, r in grp.iterrows():
            games.append({
                "date": r.get("game_date"),
                "gameId": r.get("game_id") if "game_id" in r.index else r.get("game_id"),
                "statValue": r.get("target"),
                "homeTeam": r.get("home_team"),
                "awayTeam": r.get("away_team"),
            })

        # Skip players with too few total games
        if len(games) < min_games_per_player:
            continue

        # Use the existing generator to compute features+target per game
        df_samples = generate_samples_from_game_history(pname, games, lookback=10, min_lookback=1, stat_field="statValue")
        if not df_samples.empty:
            samples_list.append(df_samples)

    if not samples_list:
        raise RuntimeError(f"No players with >={min_games_per_player} games produced samples for stat_type={stat_type}")

    all_samples = pd.concat(samples_list, ignore_index=True)

    # Ensure datetime and apply time-based splitting per player
    all_samples = all_samples.reset_index(drop=True)
    all_samples["game_date"] = pd.to_datetime(all_samples["game_date"])

    # Assign splits per player using make_time_splits on the raw rows (player_id required)
    # Note: `all_samples` contains `player` (name) but not `player_id`; map names back to ids
    # Build mapping from player name -> player_id from the grouped keys ((pid, pname) tuples).
    name_to_id = {}
    try:
        # grouped.groups.keys() yields tuples of (player_id, player_name)
        name_to_id = {pname: pid for (pid, pname) in grouped.groups.keys()}
    except Exception:
        # Fall back to empty mapping if grouping structure unexpected
        name_to_id = {}

    if "player" in all_samples.columns:
        all_samples["player_id"] = all_samples["player"].map(lambda nm: name_to_id.get(nm))

    # Fallback: if player_id missing, skip make_time_splits and just save
    try:
        all_with_splits = make_time_splits(all_samples)
    except Exception:
        all_with_splits = all_samples

    meta = save_dataset_version(all_with_splits, Path(out_dir), stat_type)
    return meta


def _parse_player_ids(s: Optional[str]) -> Optional[List[int]]:
    if not s:
        return None
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def get_distinct_stat_types() -> List[str]:
    """Return a list of distinct stat_type values available in DB.

    This is synchronous helper that uses the async engine connection
    synchronously via a short-lived event loop when called from CLI.
    """
    db._ensure_engine_and_session()
    async def _inner():
        async with db.engine.connect() as conn:
            res = await conn.execute(text("SELECT DISTINCT stat_type FROM player_stats"))
            rows = res.all()
            return [r[0] for r in rows]

    return asyncio.run(_inner())


def _cli() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stat-types", help="comma-separated stat types to generate (e.g. points,rebounds)")
    group.add_argument("--all", action="store_true", help="generate datasets for all distinct stat types in DB")
    parser.add_argument("--players", help="comma-separated player ids (optional)")
    parser.add_argument("--out-dir", default="backend/data/training_datasets")
    parser.add_argument("--min-games", type=int, default=50)
    args = parser.parse_args()

    player_ids = _parse_player_ids(args.players)

    if args.all:
        stat_types = get_distinct_stat_types()
    else:
        stat_types = [s.strip() for s in (args.stat_types or "").split(",") if s.strip()]

    if not stat_types:
        print("No stat types specified or found in DB.")
        return 2

    async def _main():
        db._ensure_engine_and_session()
        results = []
        for st in stat_types:
            try:
                meta = await generate_and_save_dataset(
                    stat_type=st,
                    player_ids=player_ids,
                    out_dir=args.out_dir,
                    min_games_per_player=args.min_games,
                )
                results.append(meta)
            except Exception as e:
                results.append({"stat_type": st, "error": str(e)})
        return results

    metas = asyncio.run(_main())
    print(json.dumps(metas, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
