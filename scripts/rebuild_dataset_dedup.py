"""Rebuild dataset by deduplicating (player, game_date) then re-splitting.

Usage:
  python scripts/rebuild_dataset_dedup.py --manifest <existing_manifest.json> --name <new_name_suffix>

This will:
 - load train/val/test features.parquet from manifest
 - concat, dedupe by (player, game_date) using mean(target)
 - run `per_player_time_split` to produce splits
 - call `dataset_versioning.create_dataset_version` to write and register
"""

import argparse
from pathlib import Path

import pandas as pd

from backend.services import dataset_versioning
from backend.services import training_data_service as tds


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--name-suffix", default="dedup")
    p.add_argument("--stat", default="points")
    args = p.parse_args()

    mpath = Path(args.manifest)
    if not mpath.exists():
        raise SystemExit("manifest not found")
    manifest = None
    import json

    with open(mpath, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    parts = manifest.get("parts", {})
    dfs = []
    for k in ["train", "val", "test"]:
        part = parts.get(k)
        if not part:
            continue
        f = Path(part["files"]["features"])
        df = pd.read_parquet(f)
        dfs.append(df)
    if not dfs:
        raise SystemExit("no feature files found")
    big = pd.concat(dfs, ignore_index=True)
    # ensure game_date datetime
    if "game_date" in big.columns:
        big["game_date"] = pd.to_datetime(big["game_date"])
    # dedupe: group by player + game_date, aggregate mean of target
    dedup = big.groupby(["player", "game_date"], as_index=False).agg({"target": "mean"})
    print("Original rows:", len(big), "Deduped rows:", len(dedup))

    # re-split
    train_df, val_df, test_df = tds.per_player_time_split(
        dedup, player_col="player", date_col="game_date"
    )
    base_name = manifest.get("name", "dataset") + "_" + args.name_suffix
    seasons = manifest.get("seasons", "")
    out = dataset_versioning.create_dataset_version(
        base_name,
        seasons,
        train_df,
        val_df,
        test_df,
        output_dir=str(Path("backend/data/datasets")),
    )
    print("Wrote new manifest:", out.get("manifest"))


if __name__ == "__main__":
    main()
