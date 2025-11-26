from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.db import Base


class PlayerStat(Base):
    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    stat_type = Column(String(64), nullable=False, index=True)
    value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    player = relationship("Player", backref="stats")
    game = relationship("Game", backref="player_stats")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<PlayerStat id={self.id} player_id={self.player_id} game_id={self.game_id} {self.stat_type}={self.value}>"
