import asyncio
import contextlib
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Garantizar que la raíz del workspace y backend_case estén en sys.path
_current_file = Path(__file__).resolve()
_backend_case_dir = _current_file.parent.parent  # backend_case/
_project_root = _backend_case_dir.parent  # software-exam1/

for _p in [str(_project_root), str(_backend_case_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv

load_dotenv(_backend_case_dir / ".env")
load_dotenv(_project_root / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import api_router
from .assistant.api.routes import router as assistant_router
from .collaboration import (
    CollaborationRoom,
    InMemoryCollaborationRoom,
    InMemoryLockStore,
    InMemoryPresenceService,
    LockStore,
    PresenceService,
    RedisCollaborationRoom,
    RedisLockStore,
    RedisPresenceService,
    collaboration_ws_router,
)
from .generation.api.routes import router as generation_router
from .interoperability.api.routes import router as interoperability_router
from .legacy.api_router import legacy_api_router
from .legacy.database import init_legacy_db
from .legacy.signaling_manager import signaling_manager
from .legacy.ws_router import legacy_ws_router
from .modeling.api import router as modeling_router
from .shared.db.base import init_db
from .shared.errors import register_exception_handlers
from .shared.security import auth_router


async def _build_collaboration_infra(
    redis_url: str,
) -> tuple[LockStore, PresenceService, CollaborationRoom, Any | None]:
    """
    Construye los adaptadores de infraestructura para colaboración (Locks, Presencia, Fan-Out).
    - Si `redis_url` está vacía: retorna adaptadores en memoria (modo local / tests).
    - Si `redis_url` está definida: intenta conectar a Redis y hace ping con timeout de 5.0s.
      Si falla o supera el timeout, lanza RuntimeError explícito (fail-fast, igual que JWT_SECRET).
    """
    if not redis_url:
        return (
            InMemoryLockStore(),
            InMemoryPresenceService(),
            InMemoryCollaborationRoom(),
            None,
        )

    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await asyncio.wait_for(redis_client.ping(), timeout=5.0)
    except Exception as exc:
        with contextlib.suppress(Exception):
            await redis_client.aclose()
        raise RuntimeError(
            f"REDIS_URL está configurada ('{redis_url}') pero Redis no responde o excedió "
            f"el timeout de 5.0s ({exc}). La app no puede arrancar en modo multi-worker sin Redis."
        ) from exc

    return (
        RedisLockStore(redis_client),
        RedisPresenceService(redis_client),
        RedisCollaborationRoom(redis_client),
        redis_client,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Initialize shared database tables on startup
    await init_db()
    # Initialize legacy database tables on startup
    await init_legacy_db()  # type: ignore[no-untyped-call]
    # Initialize Redis for multi-worker WebRTC signaling if configured
    await signaling_manager.init_redis()  # type: ignore[no-untyped-call]

    # Inicializar adaptadores de colaboración según REDIS_URL
    redis_url = os.getenv("REDIS_URL", "").strip()
    lock_store, presence_service, room, redis_client = await _build_collaboration_infra(redis_url)
    app.state.lock_store = lock_store
    app.state.presence_service = presence_service
    app.state.collaboration_room = room
    app.state.redis_client = redis_client

    try:
        yield
    finally:
        if isinstance(app.state.collaboration_room, RedisCollaborationRoom):
            await app.state.collaboration_room.close()
        if getattr(app.state, "redis_client", None) is not None:
            await app.state.redis_client.aclose()
        await signaling_manager.close_redis()  # type: ignore[no-untyped-call]


app = FastAPI(
    title="CASE UML 2.5 Backend API",
    version="2.0.0",
    description="Backend principal del CASE colaborativo - Gateway y Orquestador de Dominio",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configuración de CORS con soporte para cookies y credenciales
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sin esto, un fetch/XHR cross-origin (localhost:4200 -> :8000) no puede leer
    # el header Content-Disposition de una respuesta -- el navegador lo oculta a
    # JS aunque venga en la respuesta real (CU10/CU8: descarga de archivos).
    expose_headers=["Content-Disposition"],
)

# Registrar manejadores de error canónicos de dominio
register_exception_handlers(app)

# Registrar rutas experimentales V2
app.include_router(api_router)
app.include_router(modeling_router, prefix="/api/v2")
app.include_router(assistant_router, prefix="/api/v2")
app.include_router(interoperability_router, prefix="/api/v2")
app.include_router(generation_router, prefix="/api/v2")
app.include_router(auth_router, prefix="/api/v2")

# Canal de colaboración del stack activo (ADR-0003, paso 1: solo transporte)
app.include_router(collaboration_ws_router)

# Registrar rutas de compatibilidad legacy (Django REST + WebSockets)
app.include_router(legacy_api_router)
app.include_router(legacy_ws_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
