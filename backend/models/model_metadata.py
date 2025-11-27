from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from backend.db import Base


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    version = Column(String(64), nullable=True)
    path = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)
    # Keep a JSON list of contextual features retained for this model (nullable)
    kept_contextual_features = Column(JSON, nullable=True)
    # Canonical feature list used to train/serve this model
    feature_list = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"<ModelMetadata id={self.id} name={self.name!r} version={self.version!r}>"
        )
