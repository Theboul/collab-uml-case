"""
Módulo de rutas API.
"""

from fastapi import APIRouter

from .health import router as health_router
from .info import router as info_router
from .uml import router as uml_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(info_router)
api_router.include_router(uml_router)

__all__ = ["api_router"]
