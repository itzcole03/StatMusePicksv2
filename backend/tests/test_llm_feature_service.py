import json

from backend.services.llm_feature_service import LLMFeatureService


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        # pop next response
        if not self.responses:
            return None
        return self.responses.pop(0)


def test_extract_from_text_parses_dict(monkeypatch):
    fake = FakeClient(
        [
            {
                "injury_status": "questionable",
                "morale_score": 80,
                "news_sentiment": 0.2,
                "trade_sentiment": -0.1,
                "motivation": 0.8,
            }
        ]
    )

    # patch the name imported into llm_feature_service module
    monkeypatch.setattr(
        "backend.services.llm_feature_service.get_default_client", lambda: fake
    )

    svc = LLMFeatureService()
    out = svc.extract_from_text(
        "Some Player", "Some context mentioning nothing important."
    )
    assert out["injury_status"] == "questionable"
    assert out["morale_score"] == 80
    assert abs(out["news_sentiment"] - 0.2) < 1e-6


def test_extract_from_text_parses_json_string(monkeypatch):
    payload = json.dumps(
        {
            "injury_status": "healthy",
            "morale_score": 45,
            "news_sentiment": -0.3,
            "trade_sentiment": 0.0,
            "motivation": 0.4,
        }
    )
    fake = FakeClient([payload])
    monkeypatch.setattr(
        "backend.services.llm_feature_service.get_default_client", lambda: fake
    )

    svc = LLMFeatureService()
    out = svc.extract_from_text("Some Player", "Another context.")
    assert out["injury_status"] == "healthy"
    assert out["morale_score"] == 45
    assert abs(out["news_sentiment"] + 0.3) < 1e-6


def test_fetch_news_and_extract_normalizes_and_caches(monkeypatch):
    # client returns morale_score 90 -> normalized to (90-50)/50 = 0.8
    fake = FakeClient(
        [
            {
                "injury_status": "healthy",
                "morale_score": 90,
                "news_sentiment": 0.1,
                "trade_sentiment": 0.0,
                "motivation": 1.0,
            }
        ]
    )
    monkeypatch.setattr(
        "backend.services.llm_feature_service.get_default_client", lambda: fake
    )

    svc = LLMFeatureService()

    def fetcher(name):
        return "Routine update with good morale"

    out1 = svc.fetch_news_and_extract("PlayerX", "src1", fetcher)
    # morale normalized to ~0.8
    assert abs(out1["morale_score"] - 0.8) < 1e-6
    assert out1["injury_sentiment"] == 0.1

    # second call should be served from cache; client.calls should remain 1
    out2 = svc.fetch_news_and_extract("PlayerX", "src1", fetcher)
    assert out1 == out2
    assert fake.calls == 1


import pytest

from backend.services.llm_feature_service import LLMFeatureService


def dummy_text_fetcher(player_name: str) -> str:
    # Return deterministic text depending on player name for test coverage
    if "Injured" in player_name:
        return (
            f"{player_name} suffered an injury and is questionable for the next game."
        )
    if "Motivated" in player_name:
        return f"{player_name} is highly motivated after contract talks."
    if "Coach" in player_name:
        return f"{player_name} may be affected by a recent coaching change."
    return f"{player_name} had a routine practice, nothing notable."


@pytest.mark.parametrize(
    "names",
    [
        [f"Player{i}" for i in range(10)],
        [
            "Injured_Player",
            "Motivated_Player",
            "Coach_Player",
            "Neutral_Player",
            "Player_A",
            "Player_B",
        ],
    ],
)
def test_fetch_news_and_extract_basic(names):
    svc = LLMFeatureService()
    results = {}
    for n in names:
        res = svc.fetch_news_and_extract(
            n, source_id="test", text_fetcher=dummy_text_fetcher
        )
        # basic shape
        assert isinstance(res, dict)
        for k in (
            "injury_sentiment",
            "morale_score",
            "motivation",
            "coaching_change_impact",
        ):
            assert k in res
            assert isinstance(res[k], float)
        results[n] = res

    # caching: second call should return same values
    for n in names:
        res2 = svc.fetch_news_and_extract(
            n, source_id="test", text_fetcher=dummy_text_fetcher
        )
        assert res2 == results[n]
