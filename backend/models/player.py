from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from backend.db import Base


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    nba_player_id = Column(Integer, nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    team = Column(String(64), nullable=True)
    position = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Player id={self.id} name={self.name!r}>"
