import time
import asyncio
import numpy as np

from backend.services.ml_prediction_service import PlayerModelRegistry, MLPredictionService


class DummyPredictor:
    def predict(self, X):
        # very small deterministic computation
        return np.array([25.0])


def test_inference_latency_with_preloaded_model():
    registry = PlayerModelRegistry()
    # register a dummy predictor for 'Preloaded Player'
    registry.save_model('Preloaded Player', DummyPredictor(), persist=False)

    svc = MLPredictionService(registry=registry)

    async def run_many(n=20):
        t0 = time.perf_counter()
        for i in range(n):
            res = await svc.predict('Preloaded Player', 'points', 20.0, player_data={'seasonAvg': 24.0})
            assert 'over_probability' in res
        return time.perf_counter() - t0

    elapsed = asyncio.get_event_loop().run_until_complete(run_many(20))
    avg = elapsed / 20.0
    # Expect inference-only average under 0.1s locally; this is permissive for CI
    assert avg < 0.5
