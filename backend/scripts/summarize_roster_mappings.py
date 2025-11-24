"""Produce a CSV summarizing roster -> manifest mappings and ambiguity flags.

Writes `backend/models_store/roster_mapping_summary.csv` with columns:
- roster_name, manifest_match, resolved_player_id, mapping_method

"""
from pathlib import Path
import csv
import sys
import argparse
import os
import pandas as pd

# ensure repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.scripts.train_orchestrator_roster import fetch_roster_names, map_roster_to_manifest


def main(manifest: str, out_csv: str):
    # Prefer local mismatch/alias CSVs for roster names to avoid external API calls
    roster = []
    mismatch_paths = [
        Path('backend/models_store/roster_run/roster_mapping_mismatch.csv'),
        Path('backend/models_store/roster_run_alias_subset/roster_mapping_mismatch.csv'),
    ]
    alias_path = Path('backend/models_store/roster_alias_table.csv')

    # Try alias csv first
    if alias_path.exists():
        try:
            adf = pd.read_csv(alias_path)
            roster = adf['roster_name'].astype(str).tolist()
        except Exception:
            roster = []

    # Fallback to mismatch CSVs if alias not present
    if not roster:
        for mp in mismatch_paths:
            if mp.exists():
                try:
                    mdf = pd.read_csv(mp)
                    roster = mdf['roster_name'].astype(str).tolist()
                    break
                except Exception:
                    continue

    # Final fallback to fetch_roster_names (may call NBA API)
    if not roster:
        roster = fetch_roster_names()

    mapped = map_roster_to_manifest(manifest, roster)

    # Load local alias/mismatch CSVs to avoid making many external API calls
    alias_path = Path('backend/models_store/roster_alias_table.csv')
    mismatch_paths = [
        Path('backend/models_store/roster_run/roster_mapping_mismatch.csv'),
        Path('backend/models_store/roster_run_alias_subset/roster_mapping_mismatch.csv'),
    ]

    alias_map = {}
    if alias_path.exists():
        try:
            adf = pd.read_csv(alias_path)
            for _, r in adf.iterrows():
                alias_map[str(r.get('roster_name'))] = str(r.get('resolved_player_id'))
        except Exception:
            alias_map = {}

    mismatch_map = {}
    for mp in mismatch_paths:
        if mp.exists():
            try:
                mdf = pd.read_csv(mp)
                for _, r in mdf.iterrows():
                    # prefer explicit numeric ids
                    pid = r.get('resolved_player_id')
                    if pd.notna(pid) and str(pid).strip() != '':
                        mismatch_map[str(r.get('roster_name'))] = str(pid)
            except Exception:
                continue

    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='', encoding='utf8') as fh:
        writer = csv.DictWriter(fh, fieldnames=['roster_name', 'manifest_match', 'resolved_player_id', 'mapping_method'])
        writer.writeheader()
        for r in roster:
            match = mapped.get(r)
            pid = alias_map.get(r) or mismatch_map.get(r) or ''
            if pid:
                if match:
                    method = 'alias+manifest'
                else:
                    method = 'alias'
            else:
                method = 'manifest' if match else 'none'
            writer.writerow({'roster_name': r, 'manifest_match': match or '', 'resolved_player_id': pid, 'mapping_method': method})

    print(f"Wrote mapping summary to {out}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', default='backend/data/datasets/points_dataset_v20251121T235153Z_c71436ea/dataset_manifest.json')
    p.add_argument('--out-csv', default='backend/models_store/roster_mapping_summary.csv')
    args = p.parse_args()
    main(args.manifest, args.out_csv)
