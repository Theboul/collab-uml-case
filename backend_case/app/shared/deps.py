"""
Inyección de dependencias transversal para FastAPI.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasRepository
from backend_case.app.shared.db.base import get_db_session


def get_canvas_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> CanvasService:
    """
    Inyecta una instancia de CanvasService con el repositorio configurado sobre la sesión actual.
    """
    repository = CanvasRepository(session)
    return CanvasService(repository)
