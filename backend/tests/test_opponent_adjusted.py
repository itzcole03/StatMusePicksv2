import pytest

from backend.services.feature_engineering import _calculate_opponent_adjusted


def test_opponent_adjusted_simple():
    recent = [
        {
            "date": "2025-11-01",
            "statValue": 20,
            "opponentTeamId": "BOS",
            "opponentDefRating": 105.0,
        },
        {
            "date": "2025-10-28",
            "statValue": 25,
            "opponentTeamId": "NYK",
            "opponentDefRating": 110.0,
        },
        {
            "date": "2025-10-25",
            "statValue": 30,
            "opponentTeamId": "BOS",
            "opponentDefRating": 105.0,
        },
    ]

    opponent = {"teamId": "BOS", "defensiveRating": 105.0}

    out = _calculate_opponent_adjusted(recent, opponent)

    assert out["games_vs_current_opponent"] == 2
    assert pytest.approx(out["avg_vs_current_opponent"]) == (20 + 30) / 2
    # avg vs stronger (def <= 105) -> both BOS games match
    assert pytest.approx(out["avg_vs_stronger_def"]) == (20 + 30) / 2
    # similar within +/-2 -> opp_def 105 equals current
    assert pytest.approx(out["avg_vs_similar_def"]) == (20 + 30) / 2
    assert out["last_game_vs_current_opponent_date"] == "2025-11-01"
    assert out["last_game_vs_current_opponent_stat"] == 20.0


def test_opponent_adjusted_no_recent():
    out = _calculate_opponent_adjusted([], {"teamId": "BOS", "defensiveRating": 105.0})
    assert out["games_vs_current_opponent"] == 0
    assert out["avg_vs_current_opponent"] is None
