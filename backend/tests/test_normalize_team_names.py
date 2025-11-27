from backend.services.data_ingestion_service import normalize_raw_game


def test_full_name_to_abbrev():
    raw = {
        "homeTeam": "Los Angeles Lakers",
        "awayTeam": "Boston Celtics",
        "date": "2025-11-12T19:30:00",
    }
    out = normalize_raw_game(raw)
    assert out.get("home_team") == "LAL"
    assert out.get("away_team") == "BOS"


def test_shortname_to_abbrev():
    raw = {"home": "Lakers", "away": "Warriors", "date": "2025-11-12T19:30:00"}
    out = normalize_raw_game(raw)
    assert out.get("home_team") == "LAL"
    assert out.get("away_team") == "GSW"


def test_already_abbrev_kept():
    raw = {"home_team": "NYK", "away_team": "CHI", "date": "2025-11-12T19:30:00"}
    out = normalize_raw_game(raw)
    assert out.get("home_team") == "NYK"
    assert out.get("away_team") == "CHI"
