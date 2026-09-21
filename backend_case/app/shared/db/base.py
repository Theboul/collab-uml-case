"""
Infraestructura de base de datos compartida para FastAPI (PostgreSQL / SQLite async).
"""

import logging
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()

# Unificar el módulo en sys.modules para evitar instancias duplicadas de Base cuando
# se importa como 'app.shared.db.base' y como 'backend_case.app.shared.db.base'
if "backend_case.app.shared.db.base" not in sys.modules:
    sys.modules["backend_case.app.shared.db.base"] = sys.modules[__name__]
if "app.shared.db.base" not in sys.modules:
    sys.modules["app.shared.db.base"] = sys.modules[__name__]


def get_database_url() -> str:
    """
    Obtiene la URL de conexión a la base de datos desde DATABASE_URL o variables POSTGRES_*.
    Garantiza que rutas SQLite relativas se resuelvan siempre contra backend_case/.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent  # backend_case/
    url = os.getenv("DATABASE_URL")
    if not url and os.getenv("POSTGRES_HOST"):
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "uml_bd")
        auth = f"{user}:{password}@" if password else f"{user}@"
        url = f"postgresql+psycopg://{auth}{host}:{port}/{db}"

    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("sqlite+aiosqlite:///./"):
            rel_name = url.replace("sqlite+aiosqlite:///./", "")
            db_path = (base_dir / rel_name).resolve()
            return f"sqlite+aiosqlite:///{db_path.as_posix()}"
        return url

    default_db = (base_dir / "shared_case.db").resolve()
    return f"sqlite+aiosqlite:///{default_db.as_posix()}"


engine = create_async_engine(get_database_url(), echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """
    Inicializa las tablas de los modelos SQLAlchemy registrados en Base.
    """
    # Asegurar registro de todos los modelos en Base.metadata
    from ...modeling.infrastructure import db_models as _canvas_models  # noqa: F401
    from ..security import models as _sec_models  # noqa: F401

    if "postgresql" in str(engine.url):
        # Usar session-level advisory lock para garantizar que ningún worker evalúe
        # create_all hasta que el worker previo haya confirmado su transacción DDL.
        async with engine.connect() as lock_conn:
            await lock_conn.execute(text("SELECT pg_advisory_lock(71423891);"))
            try:
                async with engine.begin() as conn:
                    try:
                        await conn.run_sync(Base.metadata.create_all)
                    except Exception as exc:
                        if "already exists" in str(exc):
                            logger.info(
                                "Tablas o índices ya creados por worker concurrente: %s", exc
                            )
                        else:
                            raise
            finally:
                await lock_conn.execute(text("SELECT pg_advisory_unlock(71423891);"))
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Migración segura para columnas nuevas en desarrollo con SQLite
            if "sqlite" in str(engine.url):
                for col, col_type in [("owner_id", "VARCHAR(36)"), ("room_name", "VARCHAR(100)")]:
                    try:
                        await conn.execute(
                            text(f"ALTER TABLE canvases ADD COLUMN {col} {col_type}")
                        )
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
