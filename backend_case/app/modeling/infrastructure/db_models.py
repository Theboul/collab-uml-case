"""
Modelos ORM de SQLAlchemy para el módulo modeling (tabla canvases).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from backend_case.app.shared.db.base import Base


class CanvasORM(Base):
    """
    Entidad de persistencia relacional para el lienzo UML.
    Almacena los metadatos relacionales y el árbol semántico del modelo en formato JSON/JSONB.
    """

    __tablename__ = "canvases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, default="Diagrama Sin Título")
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    semantic_model = Column(JSON, nullable=False)
    visual_layout = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<CanvasORM(id='{self.id}', name='{self.name}', version={self.version})>"
