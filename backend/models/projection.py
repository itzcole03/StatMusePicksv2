from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.db import Base


class Projection(Base):
    __tablename__ = "projections"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    source = Column(String(128), nullable=True)
    stat = Column(String(64), nullable=False, index=True)
    line = Column(Float, nullable=False)
    projection_at = Column(DateTime, default=datetime.utcnow)
    raw = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("Player", backref="projections")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Projection id={self.id} player_id={self.player_id} stat={self.stat} line={self.line}>"
