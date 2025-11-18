import pandas as pd


def make_redis_stub(store=None):
    store = store or {}

    class Stub:
        def get(self, k):
            return store.get(k)

        def setex(self, k, ttl, v):
            store[k] = v

    return Stub()


def test_generate_training_data_includes_multi_features(monkeypatch):
    from backend.services import training_data_service as tds

    # Mock nba_stats_client behaviors
    monkeypatch.setattr('backend.services.training_data_service.nba_stats_client.find_player_id_by_name', lambda name: 42)

    # Provide two seasons worth of games (>= min_games)
    def fake_fetch_multi(pid, seasons=None, limit_per_season=500):
        # produce 25 games total
        out = []
        for i in range(25):
            out.append({'GAME_DATE': f'2023-11-{i+1:02d}', 'PTS': 10 + i})
        return out

    monkeypatch.setattr('backend.services.training_data_service.nba_stats_client.fetch_recent_games_multi', fake_fetch_multi)

    # Advanced aggregated
    monkeypatch.setattr('backend.services.training_data_service.nba_stats_client.get_advanced_player_stats_multi', lambda pid, seasons: {'aggregated': {'PER': 14.5, 'TS_PCT': 0.55}})
    monkeypatch.setattr('backend.services.training_data_service.nba_stats_client.get_player_season_stats_multi', lambda pid, seasons: {s: {'PTS': 20.0 + idx} for idx, s in enumerate(seasons)})

    df = tds.generate_training_data('Some Player', stat='points', min_games=10, fetch_limit=500, seasons=['2023-24', '2022-23'])
    assert isinstance(df, pd.DataFrame)
    # Expect the aggregated multi columns to be present
    assert 'multi_PER' in df.columns
    assert 'multi_TS_PCT' in df.columns
    assert 'multi_season_PTS_avg' in df.columns
    # Values should match mocked aggregates
    assert abs(df['multi_PER'].iloc[0] - 14.5) < 1e-6
    assert abs(df['multi_TS_PCT'].iloc[0] - 0.55) < 1e-6
