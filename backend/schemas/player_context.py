from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional, Any

try:
    from pydantic import ConfigDict
except Exception:
    ConfigDict = None


class RecentGame(BaseModel):
    date: Optional[str] = None
    statValue: Optional[float] = None
    # allow additional fields returned by nba_api
    extra: Optional[Any] = None


class PlayerContextResponse(BaseModel):
    player: str
    player_id: Optional[int]
    recentGames: List[dict] = Field(default_factory=list)
    seasonAvg: Optional[float]
    rollingAverages: Optional[dict] = None
    contextualFactors: Optional[dict] = None
    opponentInfo: Optional[dict] = None
    fetchedAt: int
    cached: bool = False


# Provide Pydantic v2-compatible model config when available while remaining
# compatible with Pydantic v1 deployments.
if ConfigDict is not None:
    PlayerContextResponse.model_config = ConfigDict(json_schema_extra={
        "example": {
            "player": "LeBron James",
            "player_id": 2544,
            "recentGames": [],
            "seasonAvg": 27.5,
            "fetchedAt": 0,
            "cached": False,
        }
    })
