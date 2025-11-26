"""Finalize dataset: convert datetimes, compute stats, and register in DB.

Usage:
  python scripts/finalize_dataset.py --manifest backend/data/datasets/points_dataset_v20251119T043328Z_fcb745d9/dataset_manifest.json

This will:
 - load train/val/test parquet files
 - ensure `game_date` is datetime and rewrite parquet with pyarrow
 - compute summary stats and write `dataset_summary.json` next to manifest
 - insert a metadata row into DATABASE_URL DB's `dataset_versions` table (if writable)
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from sqlalchemy import create_engine, text
except Exception:
    create_engine = None


def load_manifest(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def convert_and_rewrite(parquet_path: Path):
    df = pd.read_parquet(parquet_path)
    if "game_date" in df.columns:
        # convert to datetime
        df["game_date"] = pd.to_datetime(df["game_date"])
        # ensure timezone-naive UTC
        if df["game_date"].dt.tz is not None:
            df["game_date"] = df["game_date"].dt.tz_convert("UTC").dt.tz_localize(None)
    # rewrite using pyarrow if available
    df.to_parquet(parquet_path, index=False)
    return df


def compute_stats(train_df, val_df, test_df):
    out = {}
    out["rows_train"] = len(train_df)
    out["rows_val"] = len(val_df)
    out["rows_test"] = len(test_df)
    combined = pd.concat([train_df, val_df, test_df], ignore_index=True)
    out["rows_total"] = len(combined)
    # target stats
    out["target_mean"] = float(combined["target"].mean())
    out["target_std"] = float(combined["target"].std())
    out["target_quantiles"] = (
        combined["target"].quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).to_dict()
    )
    # per-player counts
    per_player = combined.groupby("player").size().sort_values(ascending=False)
    out["num_players"] = int(per_player.shape[0])
    out["top_players"] = per_player.head(10).to_dict()
    # outliers: target > mean + 3*std or < mean - 3*std
    m = out["target_mean"]
    s = out["target_std"]
    if s and not np.isnan(s):
        up = combined[combined["target"] > (m + 3 * s)]
        down = combined[combined["target"] < (m - 3 * s)]
        out["outliers_up"] = int(len(up))
        out["outliers_down"] = int(len(down))
    else:
        out["outliers_up"] = 0
        out["outliers_down"] = 0
    return out


def register_in_db(manifest_path: Path, manifest: dict, db_url: str):
    sync_url = db_url
    if sync_url.startswith("sqlite+aiosqlite"):
        sync_url = sync_url.replace("sqlite+aiosqlite", "sqlite")
    if "+asyncpg" in sync_url:
        sync_url = sync_url.replace("+asyncpg", "")
    if create_engine is None or not sync_url:
        return False, "No DB engine available"
    engine = create_engine(sync_url)
    insert_sql = text(
        """
        INSERT INTO dataset_versions (version_id, created_at, git_sha, seasons, rows_train, rows_val, rows_test, uid, manifest, notes)
        VALUES (:version_id, :created_at, :git_sha, :seasons, :rows_train, :rows_val, :rows_test, :uid, :manifest, :notes)
        """
    )
    params = {
        "version_id": manifest.get("version"),
        "created_at": manifest.get("created_at"),
        "git_sha": os.environ.get("GIT_SHA") or os.environ.get("CI_COMMIT_SHA") or None,
        "seasons": manifest.get("seasons"),
        "rows_train": manifest.get("rows_train"),
        "rows_val": manifest.get("rows_val"),
        "rows_test": manifest.get("rows_test"),
        "uid": manifest.get("uid"),
        "manifest": json.dumps(manifest),
        "notes": None,
    }
    try:
        with engine.begin() as conn:
            conn.execute(insert_sql, params)
        return True, "Inserted"
    except Exception as e:
        return False, str(e)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument(
        "--register-db", action="store_true", help="Insert metadata into DATABASE_URL"
    )
    args = p.parse_args()

    mpath = Path(args.manifest)
    if not mpath.exists():
        raise SystemExit("Manifest not found: %s" % mpath)
    manifest = load_manifest(mpath)
    mpath.parent

    # convert parquets
    parts = manifest.get("parts", {})
    dfs = {}
    for part_key in ["train", "val", "test"]:
        part = parts.get(part_key)
        if not part:
            raise SystemExit("Missing part: %s" % part_key)
        features = Path(part["files"]["features"])
        print("Converting", features)
        df = convert_and_rewrite(features)
        dfs[part_key] = df

    # compute stats
    stats = compute_stats(dfs["train"], dfs["val"], dfs["test"])
    summary_path = mpath.parent / "dataset_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump({"manifest": manifest, "stats": stats}, fh, indent=2, default=str)
    print("Wrote summary to", summary_path)

    # register in DB
    if args.register_db:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print("DATABASE_URL not set; skipping DB registration")
        else:
            ok, msg = register_in_db(mpath, manifest, db_url)
            print("DB registration:", ok, msg)

    print("Done")


if __name__ == "__main__":
    main()
