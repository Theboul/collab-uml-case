import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base


def get_database_url() -> str:
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
        return url

    # Fallback to local SQLite async
    return "sqlite+aiosqlite:///./legacy_uml.db"


engine = create_async_engine(get_database_url(), echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_legacy_db():
    if "postgresql" in str(engine.url):
        async with engine.connect() as lock_conn:
            await lock_conn.execute(text("SELECT pg_advisory_lock(71423892);"))
            try:
                async with engine.begin() as conn:
                    try:
                        await conn.run_sync(Base.metadata.create_all)
                    except Exception as exc:
                        if "already exists" in str(exc):
                            pass
                        else:
                            raise
            finally:
                await lock_conn.execute(text("SELECT pg_advisory_unlock(71423892);"))
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_legacy_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
