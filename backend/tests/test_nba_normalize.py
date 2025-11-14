import pytest

from backend.services.nba_normalize import canonicalize_row, canonicalize_rows


def test_canonicalize_row_basic_keys():
    raw = {
        "GAME_ID": "0031400001",
        "GAME_DATE": "2024-10-15",
        "PLAYER_ID": 201939,
        "PTS": "34",
    }
    c = canonicalize_row(raw)
    assert c["game_id"] == "0031400001"
    assert c["game_date"] == "2024-10-15"
    assert c["player_id"] == 201939
    assert isinstance(c["pts"], float)


def test_canonicalize_row_alternate_keys_and_date_parsing():
    raw = {
        "gameId": "g-1",
        "gameDate": "10/15/2024",
        "playerId": "1234",
        "points": 12,
    }
    c = canonicalize_row(raw)
    assert c["game_id"] == "g-1"
    assert c["game_date"] == "2024-10-15"
    assert c["player_id"] == "1234"
    assert c["pts"] == 12.0


def test_canonicalize_rows_dedupe():
    rows = [
        {"GAME_ID": "gid1", "PLAYER_ID": 1, "PTS": 10},
        {"game_id": "gid1", "player_id": 1, "PTS": 10},
        {"game_date": "2024-10-15", "player_id": 2, "PTS": 5},
        {"gameDate": "2024-10-15", "playerId": 2, "points": 5},
    ]
    cans = canonicalize_rows(rows)
    # Expect two unique game/player pairs
    assert len(cans) == 2
    gids = { (r.get("game_id"), r.get("player_id")) for r in cans }
    assert ("gid1", "1") in gids or ("gid1", 1) in gids
