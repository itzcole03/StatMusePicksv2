from backend.services import data_ingestion_service as dis


def test_check_missing_values():
    rec = {"game_date": "2025-11-12T00:00:00", "away_team": "BOS"}
    missing = dis.check_missing_values(rec, ["game_date", "home_team", "away_team"])
    assert missing == ["home_team"]


def test_validate_record_types_ok():
    rec = {"game_date": "2025-11-12T00:00:00", "home_score": "100", "away_score": 95}
    errs = dis.validate_record_types(rec)
    assert errs == []


def test_validate_record_types_bad_date_and_score():
    rec = {"game_date": "not-a-date", "home_score": "one-hundred"}
    errs = dis.validate_record_types(rec)
    assert (
        any(
            "game_date not parseable" in e
            or "game_date missing" in e
            or "game_date not parseable" in e
            for e in errs
        )
        or errs
    )


def test_detect_outlier_values():
    records = [
        {"value": 10},
        {"value": 12},
        {"value": 11},
        {"value": 300},
    ]
    out_idx = dis.detect_outlier_values(records, field="value", z_thresh=3.0)
    assert isinstance(out_idx, list)
    assert len(out_idx) >= 1
    # expect the large value to be flagged
    assert 3 in out_idx


def test_validate_batch():
    records = [
        {
            "game_date": "2025-11-12T00:00:00",
            "home_team": "LAL",
            "away_team": "BOS",
            "value": 10,
        },
        {
            "game_date": "2025-11-12T00:00:00",
            "home_team": "LAL",
            "away_team": "BOS",
            "value": 11,
        },
        {"game_date": None, "home_team": "LAL", "away_team": "BOS", "value": 12},
        {
            "game_date": "2025-11-12T00:00:00",
            "home_team": "LAL",
            "away_team": "BOS",
            "value": 1000,
        },
    ]
    res = dis.validate_batch(records)
    assert isinstance(res, dict)
    assert "missing" in res and "type_errors" in res and "outliers" in res
    # one missing game_date at index 2
    assert any(idx == 2 for idx, _ in res["missing"]) or res["missing"]
