"""Batch training harness that calls the single-player trainer for a list.

Writes `backend/models_store/training_batch_summary.json` with per-player results.
"""
import argparse
import json
from pathlib import Path
from typing import List

from backend.scripts.train_one_player import train_and_persist


def run_batch(players: List[str]):
    out_dir = Path('backend/models_store')
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {'players': [], 'success': 0, 'failed': 0}
    for p in players:
        try:
            print(f"Training player: {p}")
            train_and_persist(p)
            summary['players'].append({'player': p, 'status': 'ok'})
            summary['success'] += 1
        except Exception as e:
            print(f"Error training {p}: {e}")
            summary['players'].append({'player': p, 'status': 'error', 'error': str(e)})
            summary['failed'] += 1

    with open(out_dir / 'training_batch_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print('Batch complete — summary written to backend/models_store/training_batch_summary.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--players', nargs='*', help='Player names to train', default=[]) 
    parser.add_argument('--players-file', help='File with player names, one per line')
    args = parser.parse_args()

    players = args.players or []
    if args.players_file:
        p = Path(args.players_file)
        if p.exists():
            players.extend([line.strip() for line in p.read_text().splitlines() if line.strip()])

    if not players:
        print('No players provided. Use --players or --players-file')
    else:
        run_batch(players)
