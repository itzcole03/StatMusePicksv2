from pydantic import BaseModel
from typing import List, Optional


class PerPlayerFallback(BaseModel):
    player: str
    pct_with_last5: float
    pct_with_last3: float
    pct_with_seasonAvg: float
    pct_fully_missing: float


class TrainingSummaryAggregates(BaseModel):
    n_players: int
    avg_pct_with_last5: float
    avg_pct_with_last3: float
    avg_pct_with_seasonAvg: float
    avg_pct_fully_missing: float
    players_with_calibration: int
    avg_raw_ece: float
    per_player: List[PerPlayerFallback] = []


class TrainingSummaryResponse(BaseModel):
    ok: bool
    aggregates: TrainingSummaryAggregates
    summary_path: Optional[str] = None
