import asyncio

from backend.services.ml_prediction_service import MLPredictionService, PlayerModelRegistry


class DummyModel:
    def __init__(self, value=27.3):
        self.value = value

    def predict(self, X):
        # ignore X, return the same prediction
        return [self.value]


async def _run():
    reg = PlayerModelRegistry()
    svc = MLPredictionService(registry=reg)
    # register dummy model for LeBron
    reg.save_model('LeBron James', DummyModel(27.3))

    res = await svc.predict('LeBron James', 'points', 25.5, {'rollingAverages': {'last5Games': 26.0}, 'seasonAvg': 27.0, 'contextualFactors': {}} , {})
    assert isinstance(res, dict)
    assert 'predicted_value' in res
    assert 'over_probability' in res and 0.0 <= res['over_probability'] <= 1.0
    assert 'under_probability' in res and abs(res['over_probability'] + res['under_probability'] - 1.0) < 1e-6
    assert 'expected_value' in res
    assert 'confidence' in res and 0.0 <= res['confidence'] <= 100.0


def test_dummy_model_prediction():
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
    finally:
        loop.close()
