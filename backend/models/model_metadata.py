from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from backend.db import Base


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    version = Column(String(64), nullable=True)
    path = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<ModelMetadata id={self.id} name={self.name!r} version={self.version!r}>"
