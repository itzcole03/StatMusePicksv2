"""Orchestrate training for a list of players sourced from NBA roster.

Fetches player names via `backend.services.nba_stats_client.fetch_all_players()`
and attempts to train per-player models from the provided dataset manifest.

This script will skip players with no training rows in the manifest and
write a CSV report similar to the main orchestrator.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

# ensure repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.scripts.train_orchestrator import _train_worker, load_manifest
from backend.services.nba_stats_client import find_player_id_by_name, fetch_all_players
import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def fetch_roster_names() -> list:
    """Return a list of current roster player names.

    Strategy:
    1. Attempt to fetch current-season rosters via `CommonTeamRoster` (preferred).
    2. On any failure, fall back to `backend.services.nba_stats_client.fetch_all_players()`.
    """
    try:
        # compute current season string like '2025-26'
        from datetime import datetime

        now = datetime.utcnow()
        year = now.year
        if now.month >= 10:
            season = f"{year}-{str((year + 1) % 100).zfill(2)}"
        else:
            season = f"{year - 1}-{str(year % 100).zfill(2)}"

        # try to use nba_api team roster endpoint (gives current season rosters)
        try:
            from nba_api.stats.static import teams as static_teams
            from nba_api.stats.endpoints import commonteamroster
        except Exception:
            # nba_api not available; fallback below
            raise

        teams = static_teams.get_teams() or []
        names = []
        for t in teams:
            try:
                team_id = t.get('id') or t.get('teamId')
                if not team_id:
                    continue
                # call CommonTeamRoster for the season; use a generous timeout when available
                roster_df = commonteamroster.CommonTeamRoster(team_id=team_id, season=season).get_data_frames()[0]
                for r in roster_df.to_dict(orient='records'):
                    # various column name variants across nba_api versions
                    n = r.get('PLAYER') or r.get('PLAYER_NAME') or r.get('player') or r.get('PLAYER_FULL_NAME')
                    if n:
                        names.append(n)
            except Exception:
                # ignore team-level failures and continue
                continue

        # deduplicate while preserving order
        seen = set()
        deduped = []
        for n in names:
            if n not in seen:
                seen.add(n)
                deduped.append(n)
        return deduped
    except Exception:
        # graceful fallback to previous behavior (all players list)
        try:
            from backend.services.nba_stats_client import fetch_all_players
            allp = fetch_all_players() or []
            names = []
            for p in allp:
                n = p.get('full_name') or p.get('fullName') or p.get('display_name')
                if n:
                    names.append(n)
            return names
        except Exception:
            return []


def _normalize(n: str) -> str:
    import re
    if not n:
        return ''
    s = n.lower()
    # remove punctuation and diacritics
    s = re.sub(r"[\.,'\"]", '', s)
    try:
        import unicodedata
        s = ''.join(ch for ch in unicodedata.normalize('NFKD', s) if not unicodedata.combining(ch))
    except Exception:
        pass
    s = re.sub(r"\s+", ' ', s).strip()
    return s


def map_roster_to_manifest(manifest_path: str, roster: list) -> dict:
    """Return mapping of roster_name -> matched manifest player name (or None).

    Strategy:
    - Resolve NBA player id via `find_player_id_by_name()`.
    - If found, use `fetch_all_players()` to get canonical full_name for that id.
    - Try exact match against manifest `player` values; if none, try normalized substring/fuzzy match.
    """
    mm = load_manifest(Path(manifest_path))
    manifest_parent = Path(manifest_path).parent
    # read train/val/test feature files to collect manifest player names
    player_set = set()
    for split in ("train", "val", "test"):
        p = mm['parts'][split]
        fp = Path(p['files']['features'])
        if not fp.is_absolute():
            fp = (manifest_parent / fp)
        try:
            df = pd.read_parquet(fp)
            player_set.update(df['player'].astype(str).unique().tolist())
        except Exception:
            continue

    # build normalized index for quick lookup
    norm_index = { _normalize(p): p for p in player_set }

    mapped = {}
    all_players_cache = None
    for rname in roster:
        mapped[rname] = None
        try:
            pid = find_player_id_by_name(rname)
        except Exception:
            pid = None

        # If we have a pid, prefer mapping by pid and require the manifest name
        # corresponds to that pid (safer than blind name matching).
        candidate_names = []
        if pid:
            try:
                if all_players_cache is None:
                    all_players_cache = fetch_all_players() or []
                for p in all_players_cache:
                    try:
                        if int(p.get('id') or p.get('playerId') or 0) == int(pid):
                            candidate_names.append(p.get('full_name') or p.get('fullName') or p.get('display_name'))
                    except Exception:
                        continue
            except Exception:
                candidate_names = []

        # always add roster name as a candidate to try fuzzy mapping
        candidate_names.append(rname)

        found = None
        # Try strict matching first (exact or normalized exact)
        for cn in candidate_names:
            if cn is None:
                continue
            if cn in player_set:
                found = cn
                break
            nn = _normalize(cn)
            if nn in norm_index:
                found = norm_index[nn]
                break

        # If not found yet, attempt normalized-substring matching but only accept
        # it when it's unambiguous (exactly one manifest candidate matches).
        if not found:
            nn = _normalize(rname)
            matches = [orig for k_norm, orig in norm_index.items() if nn and (nn in k_norm or k_norm in nn)]
            if len(matches) == 1:
                found = matches[0]

        # If we found a manifest name but also have a pid, verify the manifest name
        # aligns with that pid (defensive check). If it doesn't, discard mapping.
        if found and pid:
            try:
                # ensure cached players available
                if all_players_cache is None:
                    all_players_cache = fetch_all_players() or []
                canonical = None
                for p in all_players_cache:
                    try:
                        if int(p.get('id') or p.get('playerId') or 0) == int(pid):
                            canonical = (p.get('full_name') or p.get('fullName') or p.get('display_name'))
                            break
                    except Exception:
                        continue
                if canonical is None:
                    # couldn't resolve canonical name for pid; be conservative and drop
                    mapped[rname] = None
                else:
                    if _normalize(canonical) == _normalize(found) or canonical == found:
                        mapped[rname] = found
                    else:
                        # names disagree; do not map automatically
                        mapped[rname] = None
            except Exception:
                mapped[rname] = None
        else:
            mapped[rname] = found

    return mapped


def main(manifest: str, out_dir: str, report_csv: str, fit_calibrators: bool = False):
    manifest_path = Path(manifest)
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest}")

    m = load_manifest(manifest_path)

    roster = fetch_roster_names()
    logger.info('Fetched %d roster candidates', len(roster))

    # Inspect manifest feature files to ensure numeric `player_id` is available
    parts = {}
    has_player_id = False
    for split in ("train", "val", "test"):
        p = m["parts"][split]
        fp = Path(p["files"]["features"]) 
        if not fp.is_absolute():
            fp = manifest_path.parent / fp
        try:
            df = pd.read_parquet(fp)
            parts[split] = df
            if 'player_id' in df.columns:
                has_player_id = True
        except Exception:
            parts[split] = None

    if not has_player_id:
        # Best-practice: require numeric player_id to avoid ambiguous name collisions.
        # Produce a mismatch CSV mapping roster names -> resolved player_id (if any)
        mismatch_csv = Path(out_dir) / 'roster_mapping_mismatch.csv'
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        rows = []
        for r in roster:
            try:
                pid = find_player_id_by_name(r)
            except Exception:
                pid = None
            rows.append({'roster_name': r, 'resolved_player_id': pid})

        with open(mismatch_csv, 'w', newline='', encoding='utf8') as fh:
            writer = csv.DictWriter(fh, fieldnames=['roster_name', 'resolved_player_id'])
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

        logger.info('Manifest features missing `player_id`; wrote mismatch CSV to %s', mismatch_csv)
        logger.info('Recommend regenerating dataset manifest with `player_id` column before running roster training.')
        return

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_rows = []
    for player in roster:
        kwargs = {
            'manifest': str(manifest_path),
            'player': player,
            'out_dir': str(out_dir),
            'fit_calibrator': bool(fit_calibrators),
        }
        logger.info('Attempting train for player: %s', player)
        r = _train_worker(kwargs)
        if r:
            report_rows.append({
                'player': r.get('player'),
                'train_rows': r.get('train_rows', 0),
                'val_rows': r.get('val_rows', 0),
                'test_rows': r.get('test_rows', 0),
                'status': r.get('status'),
                'model_path': r.get('model_path'),
            })

    # write CSV
    csv_path = Path(report_csv)
    with open(csv_path, 'w', newline='', encoding='utf8') as fh:
        writer = csv.DictWriter(fh, fieldnames=['player', 'train_rows', 'val_rows', 'test_rows', 'status', 'model_path'])
        writer.writeheader()
        for r in report_rows:
            writer.writerow(r)

    logger.info('Wrote roster training report to %s', csv_path)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--out-dir', default='backend/models_store/roster')
    p.add_argument('--report-csv', default='backend/models_store/roster_report.csv')
    p.add_argument('--fit-calibrators', action='store_true')
    args = p.parse_args()
    main(args.manifest, args.out_dir, args.report_csv, fit_calibrators=args.fit_calibrators)
