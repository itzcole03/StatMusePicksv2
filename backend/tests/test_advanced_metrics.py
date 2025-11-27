import sys
import types


def test_fetch_advanced_metrics_monkeypatch(tmp_path, monkeypatch):
    # Create a fake nba_stats_client module with NBAStatsClient
    mod = types.ModuleType("backend.services.nba_stats_client")

    class FakeClient:
        def fetch_advanced_player_metrics(self, player_id):
            # return a dict with keys expected by AdvancedMetricsService
            return {
                "PER": 18.5,
                "TS_pct": 0.58,
                "USG_pct": 22.1,
                "ORtg": 110.2,
                "DRtg": 106.7,
            }

    mod.NBAStatsClient = FakeClient
    # Insert into sys.modules so advanced_metrics_service can import it
    monkeypatch.setitem(sys.modules, "backend.services.nba_stats_client", mod)

    from backend.services.advanced_metrics_service import AdvancedMetricsService

    svc = AdvancedMetricsService(redis_client=None)
    res = svc.fetch_advanced_metrics("player_123")
    assert res is not None
    assert res["PER"] == 18.5
    assert abs(res["TS_pct"] - 0.58) < 1e-6
    assert res["USG_pct"] == 22.1
    assert res["ORtg"] == 110.2
    assert res["DRtg"] == 106.7

    # second call should hit fallback cache (in-memory) and return same values
    res2 = svc.fetch_advanced_metrics("player_123")
    assert res2 == res
