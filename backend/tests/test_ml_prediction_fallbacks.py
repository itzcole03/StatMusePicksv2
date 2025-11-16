import asyncio

from backend.services.ml_prediction_service import MLPredictionService, PlayerModelRegistry


def make_player_payload(name_suffix, season_avg=None, last5=None, last3=None, is_home=None, days_rest=None):
    pdata = {}
    if season_avg is not None:
        pdata["seasonAvg"] = season_avg
    rolling = {}
    if last5 is not None:
        rolling["last5Games"] = last5
    if last3 is not None:
        rolling["last3Games"] = last3
    if rolling:
        pdata["rollingAverages"] = rolling
    ctx = {}
    if is_home is not None:
        ctx["homeAway"] = "home" if is_home else "away"
    if days_rest is not None:
        ctx["daysRest"] = days_rest
    if ctx:
        pdata["contextualFactors"] = ctx
    return f"TestPlayer_{name_suffix}", pdata


def test_fallback_predictions_for_many_players(tmp_path):
    # Use an empty model_dir so no persisted models are accidentally loaded.
    registry = PlayerModelRegistry(model_dir=str(tmp_path))
    svc = MLPredictionService(registry=registry)

    players = []
    # 1: No data at all -> should return neutral 0.5 prob and None predicted_value
    players.append(make_player_payload("nodata"))
    # 2: season average only
    players.append(make_player_payload("seasonavg", season_avg=15.2))
    # 3: last5 only
    players.append(make_player_payload("last5", last5=9.4))
    # 4: last3 only
    players.append(make_player_payload("last3", last3=12.1))
    # 5: season + last5
    players.append(make_player_payload("both", season_avg=18.0, last5=19.0))
    # 6: context only
    players.append(make_player_payload("context", is_home=True, days_rest=3))
    # 7: season low vs line
    players.append(make_player_payload("underdog", season_avg=8.0))
    # 8: season high vs line
    players.append(make_player_payload("favorite", season_avg=30.0))
    # 9: last5 with decimals
    players.append(make_player_payload("decimals", last5=11.75))
    # 10: mixed context + rolling
    players.append(make_player_payload("mixed", last5=14.0, is_home=False, days_rest=1))

    loop = asyncio.get_event_loop()

    for name, pdata in players:
        # use a conservative line so comparisons are meaningful
        line = 15.0
        resp = loop.run_until_complete(svc.predict(name, "points", line, pdata))
        assert resp.get("player") == name
        assert resp.get("stat") == "points"
        assert isinstance(resp.get("over_probability"), float)
        # fallback now uses last5Games, last3Games, or seasonAvg
        has_info = bool(
            pdata.get("seasonAvg")
            or (pdata.get("rollingAverages") and pdata.get("rollingAverages").get("last5Games") is not None)
            or (pdata.get("rollingAverages") and pdata.get("rollingAverages").get("last3Games") is not None)
        )
        if not has_info:
            assert resp.get("predicted_value") is None
            assert resp.get("over_probability") == 0.5
            assert resp.get("confidence") == 0.0
        else:
            # predicted_value should be present and probabilities sensible
            assert resp.get("predicted_value") is not None
            op = resp.get("over_probability")
            assert 0.05 <= op <= 0.95
            assert 0.0 <= resp.get("confidence") <= 100.0
