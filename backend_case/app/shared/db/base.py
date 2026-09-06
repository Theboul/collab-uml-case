"""
Infraestructura de base de datos compartida para FastAPI (PostgreSQL / SQLite async).
"""

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


def get_database_url() -> str:
    """
    Obtiene la URL de conexión a la base de datos desde DATABASE_URL o usa SQLite local por defecto.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    return "sqlite+aiosqlite:///./shared_case.db"


engine = create_async_engine(get_database_url(), echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """
    Inicializa las tablas de los modelos SQLAlchemy registrados en Base.
    """
    # Asegurar registro de modelos en Base.metadata
    import backend_case.app.modeling.infrastructure.db_models
    import backend_case.app.shared.security.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migración segura para columnas nuevas en desarrollo con SQLite
        if "sqlite" in str(engine.url):
            for col, col_type in [("owner_id", "VARCHAR(36)"), ("room_name", "VARCHAR(100)")]:
                try:
                    await conn.execute(text(f"ALTER TABLE canvases ADD COLUMN {col} {col_type}"))
                except OperationalError as err:
                    logger.debug("Columna %s ya existe en canvases: %s", col, err)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador de sesión asíncrona para inyección de dependencias en FastAPI.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
