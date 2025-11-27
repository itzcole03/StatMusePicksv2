import math
from datetime import date

from backend.services import nba_stats_client
from backend.services import per_ws_from_playbyplay as perws
from backend.services import training_data_service


def _make_sample_games():
    dates = [
        "2025-10-01",
        "2025-10-03",
        "2025-10-05",
        "2025-10-07",
        "2025-10-09",
        "2025-10-11",
    ]
    pts = [10, 20, 30, 40, 50, 60]
    games = []
    for d, p in zip(dates, pts):
        games.append(
            {
                "GAME_DATE": d,
                "PTS": p,
                "AST": 5,
                "REB": 5,
                "FGA": 10,
                "FGM": 5,
                "FTA": 2,
                "FTM": 1,
                "STL": 1,
                "BLK": 0,
                "TO": 2,
                "MIN": 30,
                "SEASON": "2025-26",
            }
        )
    return games


def test_adv_per_uses_rolling_proxy(monkeypatch):
    games = _make_sample_games()

    # monkeypatch client lookups
    monkeypatch.setattr(nba_stats_client, "find_player_id_by_name", lambda name: 999)
    monkeypatch.setattr(
        nba_stats_client, "fetch_recent_games", lambda pid, limit, season=None: games
    )
    monkeypatch.setattr(
        nba_stats_client,
        "get_advanced_player_stats_multi",
        lambda pid, seasons=None: {},
    )

    # generate training rows; use small min_games to keep test fast
    df = training_data_service.generate_training_data(
        "Test Player", stat="points", min_games=3, fetch_limit=50
    )

    assert "adv_PER" in df.columns
    assert len(df) > 0

    # Precompute per-game proxy PER using same logic as service helper
    proxies = []
    for g in games:
        agg = perws.aggregate_season_games([g])
        est = perws.compute_per_ws_from_aggregates(agg)
        proxies.append(est.get("PER_est") or 0.0)

    # For each returned training row, adv_PER should equal the decay-weighted mean of proxies from prior
    # games in same season (uses env ADV_PROXY_DECAY or default 0.8)
    import os

    try:
        decay = float(os.environ.get("ADV_PROXY_DECAY", "0.6"))
    except Exception:
        decay = 0.6

    def _decay_weighted(vals, decay_factor):
        k = len(vals)
        weights = [decay_factor ** (k - 1 - i) for i in range(k)]
        s = sum(weights)
        return sum(v * w for v, w in zip(vals, weights)) / s

    for _, row in df.iterrows():
        gd = row["game_date"]
        if isinstance(gd, date):
            s = gd.isoformat()
        else:
            s = str(gd)
        # find index in sample games
        idx = next((i for i, g in enumerate(games) if g["GAME_DATE"] == s), None)
        assert idx is not None
        # history is games[0:idx]
        hist_idx = list(range(0, idx))
        if not hist_idx:
            # no history -> adv_PER should be 0.0 (service skips if no hist_stats)
            assert math.isclose(float(row["adv_PER"]), 0.0, rel_tol=1e-6)
        else:
            vals = [proxies[i] for i in hist_idx]
            expected = _decay_weighted(vals, decay)
            assert math.isclose(float(row["adv_PER"]), expected, rel_tol=1e-6)
