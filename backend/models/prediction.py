from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.db import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    stat_type = Column(String(64), nullable=False, index=True)
    predicted_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("Player", backref="predictions")
    game = relationship("Game", backref="predictions")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Prediction id={self.id} player_id={self.player_id} stat={self.stat_type} pred={self.predicted_value} actual={self.actual_value}>"
