#!/usr/bin/env python3
"""CI helper: export a tiny dataset using the training_data_service export helper.

This script is intended to be run in CI to exercise the parquet export path
when `pyarrow` or `fastparquet` is installed. It writes into `--output-dir`.
"""
import argparse
import os
from datetime import date, timedelta
import pandas as pd

from backend.services import training_data_service as tds


def make_sample_df(n=10):
    start = date(2020, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n)]
    df = pd.DataFrame({'game_date': dates, 'feat1': list(range(n)), 'feat2': [float(i) * 0.5 for i in range(n)]})
    y = pd.Series([float(i) for i in range(n)])
    return df, y


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', default='artifacts')
    p.add_argument('--name', default='ci_sample')
    p.add_argument('--version', default=None)
    args = p.parse_args()

    df, y = make_sample_df(10)
    manifest = tds.export_dataset_with_version(df, y=y, output_dir=args.output_dir, name=args.name, version=args.version, fmt_prefer='parquet')
    print('Wrote manifest:', manifest)


if __name__ == '__main__':
    main()
