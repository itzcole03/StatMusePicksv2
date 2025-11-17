from fastapi.testclient import TestClient

from backend.main import app


def make_payload(player, line=15.0, seasonAvg=None, last5=None, last3=None):
    pdata = {}
    if seasonAvg is not None:
        pdata["seasonAvg"] = seasonAvg
    rolling = {}
    if last5 is not None:
        rolling["last5Games"] = last5
    if last3 is not None:
        rolling["last3Games"] = last3
    if rolling:
        pdata["rollingAverages"] = rolling
    return {"player": player, "stat": "points", "line": line, "player_data": pdata, "opponent_data": {}}


def test_api_predict_multiple_players():
    client = TestClient(app)

    payloads = [
        make_payload("Integration_NoData"),
        make_payload("Integration_Season", seasonAvg=16.5),
        make_payload("Integration_Last3", last3=13.2),
        make_payload("Integration_Last5", last5=18.1),
        make_payload("Integration_Mixed", last3=12.5, seasonAvg=14.0),
    ]

    for p in payloads:
        r = client.post("/api/predict", json=p)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        pred = data.get("prediction")
        assert pred is not None
        assert pred.get("player") == p["player"]
        assert "over_probability" in pred
        # predicted_value may be None for the no-data case
        assert "confidence" in pred