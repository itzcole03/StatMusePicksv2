"""Debug runner for training data generation.

Prints counts returned by `fetch_player_stat_rows` and then attempts to
generate the dataset via `generate_and_save_dataset`, printing the result.
"""
from __future__ import annotations

import asyncio
from backend.services.training_data_service import fetch_player_stat_rows, generate_and_save_dataset


async def main():
    print('Fetching player_stat_rows for stat_type=points')
    rows = await fetch_player_stat_rows('points')
    print(f'Fetched {len(rows)} rows')
    if rows:
        # print sample counts per player
        from collections import Counter

        pcounts = Counter(r.get('player_id') for r in rows)
        print('Per-player counts (sample):')
        for pid, cnt in pcounts.most_common():
            print(pid, cnt)

    try:
        print('Attempting generate_and_save_dataset --min_games_per_player=50')
        meta = await generate_and_save_dataset('points', out_dir='backend/data/training_datasets', min_games_per_player=50)
        print('Dataset meta:')
        print(meta)
    except Exception as e:
        print('generate_and_save_dataset failed:', e)


if __name__ == '__main__':
    asyncio.run(main())
