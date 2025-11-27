from datetime import datetime

from backend.services.data_ingestion_service import normalize_raw_game


def test_normalize_from_iso_string():
    raw = {"date": "2025-11-12T15:30:00"}
    out = normalize_raw_game(raw)
    assert "game_date" in out
    assert isinstance(out["game_date"], datetime)


def test_normalize_from_epoch_seconds():
    # 2025-11-12T00:00:00 UTC -> epoch seconds
    epoch = 1760428800
    out = normalize_raw_game({"timestamp": epoch})
    assert "game_date" in out
    assert isinstance(out["game_date"], datetime)


def test_normalize_from_epoch_millis():
    # milliseconds
    epoch_ms = 1760428800000
    out = normalize_raw_game({"timestamp": epoch_ms})
    assert "game_date" in out
    assert isinstance(out["game_date"], datetime)


def test_normalize_from_game_id():
    out = normalize_raw_game({"game_id": "nba_20251112_game"})
    assert "game_date" in out
    assert isinstance(out["game_date"], datetime)
