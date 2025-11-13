from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from backend.db import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    game_date = Column(DateTime, nullable=False, index=True)
    home_team = Column(String(64), nullable=False, index=True)
    away_team = Column(String(64), nullable=False, index=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Game id={self.id} {self.home_team} vs {self.away_team} on {self.game_date}>"
