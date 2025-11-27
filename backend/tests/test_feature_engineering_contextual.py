from backend.services.feature_engineering import engineer_features


def test_engineer_adds_contextual_features():
    player = {
        "recentGames": [
            {
                "statValue": 25,
                "opponentAbbrev": "DEN",
                "opponentDefRating": 105,
                "date": "2025-11-20",
            },
            {
                "statValue": 30,
                "opponentAbbrev": "LAL",
                "opponentDefRating": 110,
                "date": "2025-11-18",
            },
        ],
        "seasonAvg": 22,
        "contextualFactors": {
            "homeAway": "away",
            "daysRest": 0,
            "teamAbbrev": "LAL",
            "isNationalTV": True,
            "isPlayoff": False,
        },
        "playerName": "Test Player",
    }
    opp = {"abbrev": "DEN", "defensiveRating": 102, "teamId": "DEN", "pace": 100}
    df = engineer_features(player, opp)
    cols = set(df.columns.tolist())
    # contextual keys added by Phase 3 work
    expected = {
        "is_playoff",
        "is_national_tv",
        "is_rivalry",
        "travel_distance_km",
        "opp_altitude_m",
        "is_high_altitude_opp",
        "is_contract_year",
        "is_all_star",
        "recent_awards_count",
        "trade_sentiment",
    }
    assert expected.issubset(cols)
