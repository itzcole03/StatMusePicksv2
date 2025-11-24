import json
import os
import tempfile

from backend.services.player_tracking_service import features_for_player


def test_features_for_player_basic(tmp_path):
    # create a temporary tracking data directory
    data_dir = tmp_path / "tracking"
    data_dir.mkdir()

    # sample two-game tracking data
    sample = [
        {
            "game_date": "2025-11-01",
            "avg_speed_mps": 3.0,  # m/s -> ~6.7108 mph
            "distance_m": 5000,
            "touches": 12,
            "time_of_possession_sec": 45,
            "exp_fg_pct": 0.52,
        },
        {
            "game_date": "2025-10-30",
            "avg_speed_mph": 6.5,
            "distance_m": 4800,
            "touches": 10,
            "time_of_possession_sec": 30,
            "exp_fg_pct": 0.47,
        },
    ]

    player_name = "Test Player"
    fname = data_dir / ("test_player.json")
    with open(fname, "w", encoding="utf-8") as fh:
        json.dump(sample, fh)

    # call features_for_player with our temp data_dir
    feats = features_for_player(player_name, data_dir=str(data_dir))

    # avg_speed_mph should be mean of ~6.7108 and 6.5
    assert feats["avg_speed_mph"] is not None
    assert abs(feats["avg_speed_mph"] - ((3.0 * 2.2369362920544 + 6.5) / 2)) < 1e-6

    # distance miles: (5000 + 4800) / 1609.344 / 2
    assert feats["distance_miles_per_game"] is not None
    expected_dist = ((5000 / 1609.344) + (4800 / 1609.344)) / 2.0
    assert abs(feats["distance_miles_per_game"] - expected_dist) < 1e-6

    assert feats["touches_per_game"] == 11.0
    assert feats["time_possession_sec_per_game"] == 37.5
    assert abs(feats["exp_fg_pct"] - ((0.52 + 0.47) / 2.0)) < 1e-6


def test_features_for_player_csv(tmp_path):
    data_dir = tmp_path / "tracking"
    data_dir.mkdir()

    # create a CSV with the same two rows
    player_name = "CSV Player"
    fname = data_dir / ("csv_player.csv")
    csv_content = (
        "game_date,avg_speed_mps,distance_m,touches,time_of_possession_sec,exp_fg_pct\n"
        "2025-11-01,3.0,5000,12,45,0.52\n"
        "2025-10-30, ,4800,10,30,0.47\n"
    )
    with open(fname, "w", encoding="utf-8") as fh:
        fh.write(csv_content)

    feats = features_for_player(player_name, data_dir=str(data_dir))
    assert feats["avg_speed_mph"] is not None
    # one row had 3.0 m/s, other blank -> mean is 3.0 * 2.2369...
    assert abs(feats["avg_speed_mph"] - (3.0 * 2.2369362920544)) < 1e-6
    assert feats["touches_per_game"] is not None
