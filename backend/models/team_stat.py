from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from backend.db import Base


class TeamStat(Base):
    __tablename__ = "team_stats"

    id = Column(Integer, primary_key=True, index=True)
    team = Column(String(64), nullable=False, index=True)
    season = Column(String(16), nullable=True, index=True)
    games_count = Column(Integer, nullable=False, default=0)
    pts_for_avg = Column(Float, nullable=True)
    pts_against_avg = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<TeamStat id={self.id} team={self.team!r} season={self.season!r} games={self.games_count} pts_for={self.pts_for_avg} pts_opp={self.pts_against_avg}>"
