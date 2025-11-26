import json

from backend.services.feature_engineering import engineer_features

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
res = engineer_features(player, opp)
print(json.dumps(res.to_dict(orient="records"), indent=2))
