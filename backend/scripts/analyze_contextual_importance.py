"""CLI: analyze contextual feature importances on a dataset.

Usage:
    python backend/scripts/analyze_contextual_importance.py --input data.csv --target target --out report.csv

Supports CSV and Parquet input. Emits CSV with feature importances and a simple selected-features list.
"""

from __future__ import annotations

import argparse

import pandas as pd

from backend.services.feature_engineering import analyze_contextual_feature_importance


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--input", required=True, help="CSV or Parquet file with features + target"
    )
    p.add_argument("--target", default="target", help="Name of the target column")
    p.add_argument("--out", required=True, help="Output CSV path for importance report")
    p.add_argument(
        "--threshold",
        type=float,
        default=0.01,
        help="Importance threshold to select features",
    )
    args = p.parse_args()

    inp = str(args.input)
    if inp.endswith(".parquet") or inp.endswith(".parq"):
        df = pd.read_parquet(inp)
    else:
        df = pd.read_csv(inp)

    imps = analyze_contextual_feature_importance(df, target_col=args.target)
    if imps.empty:
        print("No contextual features found or not enough rows to analyze.")
        return

    # write full importances
    out_df = imps.reset_index()
    out_df.columns = ["feature", "importance"]
    out_df.to_csv(args.out, index=False)
    # also print selected features by threshold
    selected = out_df[out_df["importance"] >= float(args.threshold)]["feature"].tolist()
    print("Wrote importance report to:", args.out)
    print("Selected features (threshold=%s): %s" % (args.threshold, ",".join(selected)))


if __name__ == "__main__":
    main()
