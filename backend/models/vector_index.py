from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from backend.db import Base


class VectorIndex(Base):
    __tablename__ = "vector_index"

    id = Column(Integer, primary_key=True, index=True)
    vector_id = Column(String(256), nullable=False, unique=True, index=True)
    source_type = Column(
        String(64), nullable=False, index=True
    )  # e.g., 'news' or 'game'
    source_id = Column(String(256), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True, index=True)
    model = Column(String(128), nullable=True)
    store = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<VectorIndex id={self.id} vector_id={self.vector_id} source={self.source_type}:{self.source_id}>"
