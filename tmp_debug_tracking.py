import json, os
from backend.services.player_tracking_service import features_for_player

d = os.path.join(os.getcwd(), 'tmp_tracking_debug')
if not os.path.exists(d):
    os.makedirs(d)
sample = [
    {"game_date": "2025-11-01", "avg_speed_mps": 3.0, "distance_m": 5000, "touches": 12, "time_of_possession_sec": 45, "exp_fg_pct": 0.52},
    {"game_date": "2025-10-30", "avg_speed_mph": 6.5, "distance_m": 4800, "touches": 10, "time_of_possession_sec": 30, "exp_fg_pct": 0.47},
]
with open(os.path.join(d, 'test_player.json'), 'w', encoding='utf-8') as fh:
    json.dump(sample, fh)
print('wrote', os.path.join(d,'test_player.json'))
print(features_for_player('Test Player', data_dir=d))
