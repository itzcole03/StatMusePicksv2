from backend.services.data_ingestion_service import normalize_raw_game


def test_map_provider_a_fields():
    raw = {
        "homeTeam": "LAL",
        "awayTeam": "BOS",
        "homeScore": "110",
        "awayScore": "100",
        "date": "2025-11-12T19:30:00",
    }
    out = normalize_raw_game(raw)
    assert out.get("home_team") == "LAL"
    assert out.get("away_team") == "BOS"
    assert out.get("home_score") == 110
    assert out.get("away_score") == 100
    assert "game_date" in out


def test_map_provider_b_fields():
    raw = {
        "h_team": "GSW",
        "a_team": "LAL",
        "h_score": 120,
        "a_score": 115,
        "timestamp": 1760428800,
    }
    out = normalize_raw_game(raw)
    assert out.get("home_team") == "GSW"
    assert out.get("away_team") == "LAL"
    # provider B uses numeric scores already
    assert out.get("home_score") == 120
    assert out.get("away_score") == 115
    assert "game_date" in out


def test_map_mixed_keys():
    raw = {
        "home": "NYK",
        "away_team_name": "CHI",
        "home_points": "99",
        "away_points": "101",
        "game_id": "nba_20251112_game",
    }
    out = normalize_raw_game(raw)
    assert out.get("home_team") == "NYK"
    assert out.get("away_team") == "CHI"
    assert out.get("home_score") == 99
    assert out.get("away_score") == 101
    assert "game_date" in out
