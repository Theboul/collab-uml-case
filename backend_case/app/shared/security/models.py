"""
Modelos ORM de SQLAlchemy para Identidad, Autenticación, Sesiones y Proyectos.
Fuente de verdad: docs/architecture/database-schema.md y ADR-0005.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..db.base import Base


class UserORM(Base):
    """
    Identidad principal de usuario dentro del sistema SchemaCraft.
    """

    __tablename__ = "users"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    identities = relationship(
        lambda: UserIdentityORM,
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions = relationship(
        lambda: UserSessionORM,
        back_populates="user",
        cascade="all, delete-orphan",
    )
    owned_projects = relationship(
        lambda: ProjectORM,
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class UserIdentityORM(Base):
    """
    Métodos de autenticación vinculados a un usuario (contraseña, Google OIDC, etc.).
    """

    __tablename__ = "user_identities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)  # 'password' | 'google' | 'github'
    provider_user_id = Column(String(255), nullable=False)  # email para password, sub para google
    password_hash = Column(String(255), nullable=True)  # hash seguro (Argon2id/PBKDF2)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship(lambda: UserORM, back_populates="identities")

    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_identity"),
        {"extend_existing": True},
    )


class UserSessionORM(Base):
    """
    Sesiones activas y registro de tokens para revocación y logout server-side.
    """

    __tablename__ = "user_sessions"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship(lambda: UserORM, back_populates="sessions")


class ProjectORM(Base):
    """
    Proyecto de modelado que agrupa tablas, diagramas y configuración.
    """

    __tablename__ = "projects"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_name = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, default="Diagrama Sin Título")
    description = Column(Text, nullable=True)
    engine = Column(String(30), nullable=False, default="postgresql")
    version = Column(Integer, nullable=False, default=1)
    semantic_model = Column(
        JSON,
        nullable=False,
        default=lambda: {"classes": [], "relations": [], "packages": []},
    )
    visual_layout = Column(
        JSON,
        nullable=True,
        default=lambda: {"cells": []},
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_opened_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    owner = relationship(lambda: UserORM, back_populates="owned_projects")
    collaborators = relationship(
        lambda: ProjectCollaboratorORM,
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectCollaboratorORM(Base):
    """
    Asociación M:N de Colaboradores invitados a un proyecto.
    """

    __tablename__ = "project_collaborators"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
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

    project = relationship(lambda: ProjectORM, back_populates="collaborators")
    user = relationship(lambda: UserORM)
