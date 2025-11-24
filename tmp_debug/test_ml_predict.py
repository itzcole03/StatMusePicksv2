import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import asyncio
from backend.services.ml_prediction_service import MLPredictionService

svc = MLPredictionService()

async def run():
    res = await svc.predict('Test Player', 'points', 20.5, {'seasonAvg': 22.0, 'recentGames': []}, {})
    print('result:', res)

asyncio.run(run())
