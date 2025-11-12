from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import logging

from backend.services.ml_prediction_service import MLPredictionService

app = FastAPI(title="StatMusePicks ML (light)")
logger = logging.getLogger(__name__)

ml_service = MLPredictionService()


class PredictionRequest(BaseModel):
    player: str
    stat: str
    line: float
    player_data: Optional[Dict] = None
    opponent_data: Optional[Dict] = None


class PredictionResponse(BaseModel):
    player: str
    stat: str
    line: float
    predicted_value: Optional[float]
    over_probability: float
    under_probability: float
    recommendation: Optional[str]
    expected_value: float
    confidence: float


@app.post("/predict", response_model=PredictionResponse)
async def predict_prop(req: PredictionRequest):
    try:
        result = await ml_service.predict(req.player, req.stat, req.line, req.player_data or {}, req.opponent_data or {})
        # ensure minimal keys exist for the response model
        if 'predicted_value' not in result:
            result.setdefault('predicted_value', None)
        if 'expected_value' not in result:
            result.setdefault('expected_value', 0.0)
        if 'confidence' not in result:
            result.setdefault('confidence', 0.0)
        return result
    except Exception as e:
        logger.exception('prediction endpoint error')
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/health')
async def health():
    return {"status": "healthy"}
