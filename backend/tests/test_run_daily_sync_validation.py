import sys
import types
from datetime import date

import pytest

from backend.services import data_ingestion_service as dis


def test_run_daily_sync_validation_filters(monkeypatch, tmp_path):
    # create a fake provider module that returns two records: one missing home_team
    fake = types.SimpleNamespace()

    fake.fetch_yesterday_games = lambda: [
        {"game_id": "g1", "game_date": "2025-11-12T00:00:00", "away_team": "BOS", "home_team": None, "value": 10},
        {"game_id": "g2", "game_date": "2025-11-12T00:00:00", "away_team": "NYK", "home_team": "LAL", "value": 12},
    ]

    sys.modules["backend.services.nba_stats_client"] = fake

    # ensure audit dir is inside tmp_path
    monkeypatch.setenv("INGEST_AUDIT_DIR", str(tmp_path))

    res = dis.run_daily_sync(when=date(2025, 11, 12))
    assert isinstance(res, dict)
    assert "validation" in res
    # missing should include one record (index 0)
    missing = res["validation"].get("missing", [])
    assert any(i == 0 for i, _ in missing)
    # filtered_out_count should be 1
    assert res.get("filtered_out_count", 0) == 1


def test_send_alert_no_webhook_logs(monkeypatch, caplog):
    # call send_alert without webhook configured
    monkeypatch.delenv("INGEST_ALERT_WEBHOOK", raising=False)
    dis.send_alert('{"test":true}')
    # warning logged
    assert any("Alert (no webhook configured)" in r.message for r in caplog.records)
