import pytest

from backend.services.llm_feature_service import LLMFeatureService


def dummy_text_fetcher(player_name: str) -> str:
    # Return deterministic text depending on player name for test coverage
    if 'Injured' in player_name:
        return f"{player_name} suffered an injury and is questionable for the next game."
    if 'Motivated' in player_name:
        return f"{player_name} is highly motivated after contract talks."
    if 'Coach' in player_name:
        return f"{player_name} may be affected by a recent coaching change."
    return f"{player_name} had a routine practice, nothing notable."


@pytest.mark.parametrize('names', [
    [f'Player{i}' for i in range(10)],
    ['Injured_Player', 'Motivated_Player', 'Coach_Player', 'Neutral_Player', 'Player_A', 'Player_B']
])
def test_fetch_news_and_extract_basic(names):
    svc = LLMFeatureService()
    results = {}
    for n in names:
        res = svc.fetch_news_and_extract(n, source_id='test', text_fetcher=dummy_text_fetcher)
        # basic shape
        assert isinstance(res, dict)
        for k in ('injury_sentiment', 'morale_score', 'motivation', 'coaching_change_impact'):
            assert k in res
            assert isinstance(res[k], float)
        results[n] = res

    # caching: second call should return same values
    for n in names:
        res2 = svc.fetch_news_and_extract(n, source_id='test', text_fetcher=dummy_text_fetcher)
        assert res2 == results[n]
