"""
Punto de entrada principal de la aplicación FastAPI backend_case.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import api_router
from .legacy.api_router import legacy_api_router
from .legacy.database import init_legacy_db
from .legacy.signaling_manager import signaling_manager
from .legacy.ws_router import legacy_ws_router
from .modeling.api import router as modeling_router
from .shared.db.base import init_db
from .shared.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared database tables on startup
    await init_db()
    # Initialize legacy database tables on startup
    await init_legacy_db()
    # Initialize Redis for multi-worker WebRTC signaling if configured
    await signaling_manager.init_redis()
    try:
        yield
    finally:
        await signaling_manager.close_redis()


app = FastAPI(
    title="CASE UML 2.5 Backend API",
    version="2.0.0",
    description="Backend principal del sistema CASE colaborativo - Gateway y Orquestador de Dominio",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configuración de CORS paritaria con Django (CORS_ALLOW_ALL_ORIGINS = True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar manejadores de error canónicos de dominio
register_exception_handlers(app)

# Registrar rutas experimentales V2
app.include_router(api_router)
app.include_router(modeling_router, prefix="/api/v2")

# Registrar rutas de compatibilidad legacy (Django REST + WebSockets)
app.include_router(legacy_api_router)
app.include_router(legacy_ws_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

