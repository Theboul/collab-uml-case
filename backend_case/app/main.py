"""
Punto de entrada principal de la aplicación FastAPI backend_case.
"""

import sys
from pathlib import Path

# Garantizar que la raíz del workspace y backend_case estén en sys.path
_current_file = Path(__file__).resolve()
_backend_case_dir = _current_file.parent.parent  # backend_case/
_project_root = _backend_case_dir.parent        # software-exam1/

for _p in [str(_project_root), str(_backend_case_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv(_backend_case_dir / ".env")
load_dotenv(_project_root / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import api_router
from .assistant.api.routes import router as assistant_router
from .collaboration import (
    collaboration_ws_router,
    create_collaboration_room,
    create_lock_store,
    create_presence_service,
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

# Sala y servicios de colaboración del proceso; se inyectan vía dependencias.
app.state.collaboration_room = create_collaboration_room()
app.state.lock_store = create_lock_store()
app.state.presence_service = create_presence_service()

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
    # Sin esto, un fetch/XHR cross-origin (localhost:4200 -> :8001) no puede leer
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

