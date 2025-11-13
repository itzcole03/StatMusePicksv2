from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional, Any


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
    fetchedAt: int
    cached: bool = False
