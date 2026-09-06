"""
Modelos ORM de SQLAlchemy para el módulo modeling (tabla canvases).
"""

import uuid
from datetime import datetime, timezone
from typing import ClassVar

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from sqlalchemy.orm import relationship

from backend_case.app.shared.db.base import Base
from backend_case.app.shared.security.models import UserORM  # noqa: F401


class CanvasORM(Base):
    """
    Entidad de persistencia relacional para el lienzo UML.
    Almacena los metadatos relacionales y el árbol semántico del modelo en formato JSON/JSONB.
    """

    __tablename__ = "canvases"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, default="Diagrama Sin Título")
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    room_name = Column(String(100), unique=True, nullable=True, index=True)
    semantic_model = Column(JSON, nullable=False)
    visual_layout = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    collaborators = relationship(
        lambda: CanvasCollaboratorORM,
        back_populates="canvas",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CanvasORM(id='{self.id}', name='{self.name}', version={self.version})>"


class CanvasCollaboratorORM(Base):
    """
    Asociación M:N de Colaboradores incorporados a un lienzo UML mediante código o enlace (CU2).
    """

    __tablename__ = "canvas_collaborators"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    canvas_id = Column(
        String(36),
        ForeignKey("canvases.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    joined_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    canvas = relationship(lambda: CanvasORM, back_populates="collaborators")
    user = relationship(lambda: UserORM)

    def __repr__(self) -> str:
        return f"<CanvasCollaboratorORM(canvas_id='{self.canvas_id}', user_id='{self.user_id}')>"

