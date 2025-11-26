"""Export train/val/test features.parquet to CSV for downstream tooling.

Usage:
  python scripts/export_dataset_csvs.py --manifest <manifest.json> --out-dir backend/data/datasets/<name>_csv
"""

import argparse
from pathlib import Path

import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--out-dir", required=False)
    args = p.parse_args()
    import json

    mpath = Path(args.manifest)
    manifest = json.load(open(mpath, "r", encoding="utf-8"))
    base = mpath.parent
    parts = manifest.get("parts", {})
    out_base = Path(args.out_dir) if args.out_dir else base
    out_base.mkdir(parents=True, exist_ok=True)
    for k in ["train", "val", "test"]:
        pinfo = parts.get(k)
        if not pinfo:
            continue
        f = Path(pinfo["files"]["features"])
        df = pd.read_parquet(f)
        # ensure game_date is ISO string
        if "game_date" in df.columns:
            df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")
        out_path = out_base / f'{manifest.get("name")}_{k}.csv'
        df.to_csv(out_path, index=False)
        print("Wrote", out_path)


if __name__ == "__main__":
    main()
